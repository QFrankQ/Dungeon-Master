// ===================================================================================
// --- AGENTS FUNCTIONALITY ---
// ===================================================================================

// Extend app with agents methods
Object.assign(app, {
    // --- AGENTS ---
    createAgentObject(options = {}) {
        const newStatblock = this.createEmptySheet(this.getStatblockTemplate());
        // Ensure all ability arrays are initialized to prevent errors
        newStatblock.special_traits = [];
        newStatblock.actions = [];
        newStatblock.bonus_actions = [];
        newStatblock.reactions = [];
        newStatblock.lair_actions = [];
        newStatblock.legendary_actions = { uses: 0, actions: [] };
        newStatblock.mythic_actions = { trigger: '', actions: [] };
        newStatblock.stats = newStatblock.stats || {};
        newStatblock.stats.damage_vulnerabilities = [];
        newStatblock.stats.damage_resistances = [];
        newStatblock.stats.damage_immunities = [];
        newStatblock.stats.condition_immunities = [];

        return {
            id: options.id || null, // ID will be set by backend on creation
            name: options.name || 'New Agent',
            active: options.active !== undefined ? options.active : true,
            isDM: options.isDM || false,
            context: {
                notes: [],
                sheetMode: 'statblock',
                characterSheet: this.createEmptySheet(this.getCharacterSheetTemplate()),
                statblock: newStatblock,
            },
            systemPrompt: options.systemPrompt || '',
            stats: { totalTokens: 0, requestCount: 0, totalPrice: 0.00 },
            ...options
        };
    },

    async addNewAgent() {
        const newAgent = this.createAgentObject();
        
        // --- BACKEND INTEGRATION ---
        const savedAgent = await apiService.saveData('agent', newAgent);
        
        this.state.agents.push(savedAgent);
        this.renderAgents();
        // For now, skip editing - just create the agent
        // this.editAgent(savedAgent.id);
    },

    createAgentCard(agent) {
        const avgTokens = agent.stats.requestCount > 0 ? (agent.stats.totalTokens / agent.stats.requestCount).toFixed(0) : 0;
        const avgPrice = agent.stats.requestCount > 0 ? (agent.stats.totalPrice / agent.stats.requestCount).toFixed(6) : '0.00';
        
        return `
        <div class="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <label class="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" ${agent.active ? 'checked' : ''} class="sr-only peer" onchange="app.toggleAgentActive('${agent.id}')" ${agent.isDM ? 'disabled' : ''}>
                      <div class="w-11 h-6 rounded-full peer transition-colors ${agent.active ? 'bg-green-500' : 'bg-gray-300 dark:bg-gray-600'} peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all ${agent.isDM ? 'opacity-50 cursor-not-allowed' : ''}"></div>
                    </label>
                    <h3 class="text-lg font-semibold">${agent.name} ${agent.isDM ? '(DM)' : ''}</h3>
                </div>
                <div class="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                    <button onclick="app.exportAgent('${agent.id}')" class="hover:text-indigo-500 p-2 rounded-md"><i class="fas fa-download"></i></button>
                    <button onclick="document.getElementById('import-agent-input-${agent.id}').click()" class="hover:text-indigo-500 p-2 rounded-md"><i class="fas fa-upload"></i></button>
                    <input type="file" id="import-agent-input-${agent.id}" class="hidden" accept=".json" onchange="app.importAgent(event, '${agent.id}')">
                    ${!agent.isDM ? `<button onclick="app.confirmDeleteAgent('${agent.id}')" class="text-red-500 hover:text-red-700 p-2 rounded-md"><i class="fas fa-trash"></i></button>` : ''}
                </div>
            </div>
            <div class="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-600 dark:text-gray-400 grid grid-cols-2 md:grid-cols-4 gap-2">
                <div><strong>Tokens:</strong> ${agent.stats.totalTokens}</div>
                <div><strong>Requests:</strong> ${agent.stats.requestCount}</div>
                <div><strong>Avg Tokens/Req:</strong> ${avgTokens}</div>
                <div><strong>Total Price:</strong> $${agent.stats.totalPrice.toFixed(4)}</div>
            </div>
        </div>
        `;
    },
    
    toggleAgentActive(agentId) {
        const agent = this.state.agents.find(a => a.id === agentId);
        if (agent && !agent.isDM) {
            agent.active = !agent.active;
            this.renderAgents();
            apiService.saveData('agent', agent); // --- BACKEND INTEGRATION ---
        }
    },
    
    confirmDeleteAgent(agentId) {
        const agent = this.state.agents.find(a => a.id === agentId);
        if (!agent) return;
        app.showConfirmModal(`Delete ${agent.name}?`, 'Are you sure you want to delete this agent?', async () => {
            // --- BACKEND INTEGRATION ---
            await apiService.deleteData('agent', agentId);
            
            this.state.agents = this.state.agents.filter(a => a.id !== agentId);
            this.renderAgents();
        });
    },

    updateAggregateStats() {
        const activeAgents = this.state.agents.filter(a => a.active);
        const activeStats = { totalTokens: 0, requestCount: 0, totalPrice: 0 };
        activeAgents.forEach(a => {
            activeStats.totalTokens += a.stats.totalTokens;
            activeStats.requestCount += a.stats.requestCount;
            activeStats.totalPrice += a.stats.totalPrice;
        });

        const activeStatsEl = document.getElementById('active-agents-stats');
        if (activeStatsEl) {
            activeStatsEl.innerHTML = `
                <span><strong>Total Tokens:</strong> ${activeStats.totalTokens}</span>
                <span><strong>Total Requests:</strong> ${activeStats.requestCount}</span>
                <span><strong>Total Price:</strong> $${activeStats.totalPrice.toFixed(4)}</span>
            `;
        }
        
        const sessionStatsEl = document.getElementById('session-total-stats');
        if (sessionStatsEl) {
            sessionStatsEl.innerHTML = `
                <span><strong>Total Tokens:</strong> ${this.state.sessionStats.totalTokens}</span>
                <span><strong>Total Requests:</strong> ${this.state.sessionStats.requestCount}</span>
                <span><strong>Total Price:</strong> $${this.state.sessionStats.totalPrice.toFixed(4)}</span>
            `;
        }
    }
});