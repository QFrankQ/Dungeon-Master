// ===================================================================================
// --- USER PROFILE FUNCTIONALITY ---
// ===================================================================================

// Extend app with user profile methods
Object.assign(app, {
    // --- USER PROFILE ---
    async saveNote() {
        const title = document.getElementById('note-title').value.trim();
        const tags = document.getElementById('note-tags').value.trim().split(',').map(t => t.trim()).filter(t => t);
        const content = document.getElementById('note-content').value.trim();
        if (!content) { alert('Note content cannot be empty.'); return; }

        const newNote = { title, tags, content };
        
        // --- BACKEND INTEGRATION ---
        const savedNote = await apiService.saveData('note', newNote);
        
        this.state.userProfile.notes.push(savedNote);
        
        document.getElementById('note-title').value = '';
        document.getElementById('note-tags').value = '';
        document.getElementById('note-content').value = '';

        this.renderProfile();
    },

    async deleteNote(noteId) {
        app.showConfirmModal('Delete Note?', 'Are you sure you want to delete this note?', async () => {
            // --- BACKEND INTEGRATION ---
            await apiService.deleteData('note', noteId);
            
            this.state.userProfile.notes = this.state.userProfile.notes.filter(n => n.id !== noteId);
            this.renderProfile();
        });
    },

    // --- MODALS ---
    showConfirmModal(title, text, onConfirm) {
        // Simple confirm dialog for now - could be enhanced with a proper modal
        if (confirm(`${title}\n${text}`)) {
            onConfirm();
        }
    }
});