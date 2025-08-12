// ===================================================================================
// --- CHAT FUNCTIONALITY ---
// ===================================================================================

// Extend app with chat methods
Object.assign(app, {
    // --- CORE FUNCTIONALITY ---
    async sendMessage() {
        const input = document.getElementById('chat-input');
        const text = input.value.trim();
        if (!text) return;

        this.state.chatHistory.push({ sender: 'user', text });
        input.value = '';
        this.renderChat();
        
        // Show thinking indicator and disable send button
        document.getElementById('chat-thinking-indicator').classList.remove('hidden');
        document.getElementById('send-button').disabled = true;

        // --- BACKEND INTEGRATION ---
        // Call the backend to get the LLM response.
        const payload = {
            chatHistory: this.state.chatHistory,
            agents: this.state.agents,
            userProfile: this.state.userProfile,
            settings: this.state.settings.ai
        };
        const response = await apiService.getLlmResponse(payload);
        
        // Update state with the response from the backend
        this.state.chatHistory.push(response.newMessage);
        
        const agentToUpdate = this.state.agents.find(a => a.id === response.updatedAgentId);
        if (agentToUpdate) {
            agentToUpdate.stats.totalTokens += response.usageStats.tokensUsed;
            agentToUpdate.stats.requestCount++;
            agentToUpdate.stats.totalPrice += response.usageStats.price;
        }
        this.state.sessionStats.totalTokens += response.usageStats.tokensUsed;
        this.state.sessionStats.requestCount++;
        this.state.sessionStats.totalPrice += response.usageStats.price;

        // Hide thinking indicator and re-enable send button
        document.getElementById('chat-thinking-indicator').classList.add('hidden');
        document.getElementById('send-button').disabled = false;
        
        this.render(); // Re-render everything to show new message and updated stats
    },

    rollDice() {
        const count = parseInt(document.getElementById('dice-count').value);
        const type = parseInt(document.getElementById('dice-type').value);
        const resultEl = document.getElementById('dice-result');
        
        let rolls = [];
        let total = 0;
        for (let i = 0; i < count; i++) {
            const roll = Math.floor(Math.random() * type) + 1;
            rolls.push(roll);
            total += roll;
        }

        const rollsHtml = rolls.map(r => {
            let className = '';
            if (r === type) className = 'roll-max';
            if (r === 1) className = 'roll-min';
            return `<span class="${className}">${r}</span>`;
        }).join(' + ');

        if (count > 1) {
            resultEl.innerHTML = `${rollsHtml} = <strong class="ml-2">${total}</strong>`;
        } else {
            resultEl.innerHTML = rollsHtml;
        }

        const chatText = `Rolled ${count}d${type}: ${resultEl.textContent}`;
        this.state.chatHistory.push({ sender: 'System', text: chatText });
        this.renderChat();
    }
});