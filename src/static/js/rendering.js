// ===================================================================================
// --- RENDERING FUNCTIONALITY ---
// ===================================================================================

// Extend app with rendering methods
Object.assign(app, {
    // --- RENDERING ---
    render() {
        this.renderChat();
        this.renderProfile();
        this.renderAgents();
        this.renderSettings();
        this.updateActiveNav();
    },

    renderChat() {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) {
            console.error('chat-messages element not found');
            return;
        }
        
        if (!this.state.chatHistory || this.state.chatHistory.length === 0) {
            console.error('No chat history to render');
            return;
        }
        
        chatMessages.innerHTML = this.state.chatHistory.map(msg => `
            <div class="flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}">
                <div class="max-w-xl p-3 rounded-lg ${msg.sender === 'user' ? 'bg-indigo-600 text-white' : 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100'}">
                    ${msg.sender !== 'user' ? `<div class="font-bold text-sm mb-1">${msg.sender}</div>` : ''}
                    <p>${msg.text}</p>
                </div>
            </div>
        `).join('');
        chatMessages.scrollTop = chatMessages.scrollHeight;
    },
    
    renderProfile() {
        const notesList = document.getElementById('notes-list');
        notesList.innerHTML = this.state.userProfile.notes.map((note) => `
            <div class="bg-gray-100 dark:bg-gray-700/50 p-3 rounded-lg border border-gray-200 dark:border-gray-700">
                <div class="flex justify-between items-start">
                    <div>
                        <h4 class="font-semibold">${note.title || 'Untitled Note'}</h4>
                        <div class="text-xs text-gray-600 dark:text-gray-400 mt-1">${(note.tags || []).map(t => `<span class="bg-gray-300 dark:bg-gray-600 px-2 py-0.5 rounded-full">${t}</span>`).join(' ')}</div>
                    </div>
                    <button onclick="app.deleteNote('${note.id}')" class="text-red-500 hover:text-red-700 text-sm p-1"><i class="fas fa-trash"></i></button>
                </div>
                <p class="text-sm text-gray-700 dark:text-gray-300 mt-2">${note.content}</p>
            </div>
        `).join('');
        
        const formEl = document.getElementById('character-sheet-form');
        formEl.innerHTML = this.buildFormFromTemplate(this.characterSheetTemplate, this.state.userProfile.characterSheet, 'userProfile.characterSheet');
    },

    renderAgents() {
        const agentsList = document.getElementById('agents-list');
        agentsList.innerHTML = this.state.agents.map(agent => this.createAgentCard(agent)).join('');
        this.updateAggregateStats();

        const agentViewScroller = document.querySelector('#agents-view > .flex-1.overflow-y-auto');
        if (agentViewScroller && this.state.lastScrollPosition > 0) {
            agentViewScroller.scrollTop = this.state.lastScrollPosition;
            this.state.lastScrollPosition = 0; // Reset after applying
        }
    },
    
    renderSettings() {
        const toggleBtn = document.getElementById('dark-mode-toggle');
        const toggleSwitch = document.getElementById('dark-mode-switch');
        if (this.state.darkMode) {
            document.documentElement.classList.add('dark');
            toggleBtn.classList.remove('bg-gray-200');
            toggleBtn.classList.add('bg-indigo-600');
            toggleSwitch.classList.add('translate-x-5');
        } else {
            document.documentElement.classList.remove('dark');
            toggleBtn.classList.add('bg-gray-200');
            toggleBtn.classList.remove('bg-indigo-600');
            toggleSwitch.classList.remove('translate-x-5');
        }
        
        document.documentElement.style.fontSize = this.state.settings.textSize + 'px';
        document.getElementById('text-size-input').value = this.state.settings.textSize;
        document.getElementById('ai-temp').value = this.state.settings.ai.temperature;
        document.getElementById('ai-temp').nextElementSibling.textContent = this.state.settings.ai.temperature;
        document.getElementById('ai-max-output').value = this.state.settings.ai.maxOutput;
        document.getElementById('ai-price-limit').value = this.state.settings.ai.priceLimit;
    }
});