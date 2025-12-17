# Future Production Upgrades

This document tracks planned upgrades for production deployment.

## Session Lifecycle Management

**Current Status**: Development-ready simple cleanup
**Priority**: High (required before production)
**Estimated Effort**: Medium

### Problem
The current session cleanup strategy (`delete_all_active()`) is too aggressive for production:
- Deletes ALL active sessions on bot restart
- Cannot support pause/resume functionality
- No session history for analytics
- May lose active sessions during deployment

### Solution: Timeout-Based Session Lifecycle

#### 1. Database Schema Changes

Add timestamp tracking to the `Session` model:

```python
# src/persistence/models.py
class Session:
    # ... existing fields ...
    ended_at: Optional[datetime] = None  # Track when session ended
    # Note: created_at and last_activity already exist
```

**Migration Required**: Yes - add `ended_at` column

#### 2. Update Session Repository

Replace `delete_all_active()` with timeout-based cleanup:

```python
# src/persistence/repositories/session_repo.py

async def cleanup_orphaned_sessions(self, timeout_minutes: int = 30) -> int:
    """
    Clean up sessions that have been inactive for too long.

    This safely handles bot restarts and crashes while preserving:
    - Recently active sessions (< timeout)
    - Paused sessions
    - Ended sessions (for history)

    Args:
        timeout_minutes: Consider sessions orphaned after this many minutes of inactivity

    Returns:
        Number of orphaned sessions deleted
    """
    from datetime import datetime, timedelta

    cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)

    # Only delete sessions that are BOTH:
    # 1. Status is "active" (not paused or ended)
    # 2. No activity for timeout_minutes
    result = await self.session.execute(
        select(Session).where(
            Session.status == "active",
            Session.last_activity < cutoff_time
        )
    )
    sessions = list(result.scalars().all())

    for game_session in sessions:
        await self.session.delete(game_session)

    await self.session.flush()
    return len(sessions)

async def set_ended_at(self, session_id: uuid.UUID, ended_at: datetime) -> Optional[Session]:
    """Set the ended_at timestamp for a session."""
    game_session = await self.get_by_id(session_id)
    if game_session:
        game_session.ended_at = ended_at
        await self.session.flush()
    return game_session
```

#### 3. Update `/end` Command

Change from DELETE to status update:

```python
# src/discord/cogs/session_commands.py

@app_commands.command(name="end")
async def end_session(self, interaction: discord.Interaction):
    # ... existing validation ...

    # OLD (development):
    # await self.session_pool.end_session(channel_id)

    # NEW (production):
    session_context = self.session_pool.get(channel_id)
    if session_context:
        # Mark as ended in database (don't delete)
        async with get_session() as db_session:
            session_repo = SessionRepository(db_session)
            await session_repo.set_status(session_context.session_db_id, "ended")
            await session_repo.set_ended_at(session_context.session_db_id, datetime.utcnow())
            await db_session.commit()

        # Clean up in-memory resources
        await self.session_pool.end_session(channel_id)
```

#### 4. Update Bot Startup Cleanup

```python
# src/discord/bot.py

@bot.event
async def on_ready():
    # ... existing code ...

    # OLD (development):
    # deleted_count = await session_repo.delete_all_active()

    # NEW (production):
    deleted_count = await session_repo.cleanup_orphaned_sessions(timeout_minutes=30)

    # Sessions inactive for 30+ minutes are cleaned up
    # Recently active sessions are preserved (graceful restart support)
```

### Benefits

#### Immediate Benefits
- ✅ **Graceful Restarts**: Sessions active within 30min survive bot restarts
- ✅ **Session History**: Ended sessions preserved for analytics
- ✅ **Safer Deployments**: Active games aren't interrupted by deployments

#### Future Features Enabled
- ✅ **Pause/Resume**: Can add `status="paused"` without cleanup interference
- ✅ **Session Analytics**: Track session duration, player engagement, etc.
- ✅ **Multi-Instance**: Can add bot_instance_id for horizontal scaling
- ✅ **Auto-Recovery**: Sessions can auto-resume after brief disconnections

### Migration Path

1. **Add `ended_at` column** to sessions table
2. **Deploy new cleanup logic** alongside old (feature flag)
3. **Test with staging environment** (verify 30min timeout works)
4. **Switch to new logic** in production
5. **Remove old `delete_all_active()`** after validation

### Configuration

Make timeout configurable via environment variable:

```python
# .env
SESSION_TIMEOUT_MINUTES=30  # Default for production

# For development (can use shorter timeout)
SESSION_TIMEOUT_MINUTES=5
```

### Testing Checklist

Before production deployment, verify:
- [ ] Bot restart preserves sessions with last_activity < 30min ago
- [ ] Bot restart cleans sessions with last_activity > 30min ago
- [ ] `/end` sets status="ended" and ended_at timestamp
- [ ] Ended sessions are NOT cleaned up by timeout logic
- [ ] Paused sessions (future) are NOT cleaned up by timeout logic
- [ ] Analytics queries work on ended sessions

### Related Future Features

This upgrade enables:
1. **Session Pause/Resume** - `/pause` and `/resume` commands
2. **Session History** - Query past sessions for analytics
3. **Auto-Save/Recovery** - Resume sessions after brief outages
4. **Multi-Instance Support** - Horizontal scaling with session ownership

---

## Other Future Upgrades

### Persistent Character Storage
**Priority**: Medium
**Status**: Not started

Currently uploaded characters are deleted when session ends. Consider:
- Per-guild persistent character storage
- Database-backed character library
- Character versioning/backup

### Multi-Instance Deployment
**Priority**: Low (only needed at scale)
**Status**: Not started

Add `bot_instance_id` to session tracking for horizontal scaling.

### Advanced Analytics
**Priority**: Low
**Status**: Not started

With ended sessions preserved, can track:
- Average session duration
- Popular characters
- Player engagement metrics
- DM response quality (via feedback)
