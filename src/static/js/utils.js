// ===================================================================================
// --- UTILITY FUNCTIONS ---
// ===================================================================================

// Extend app with utility methods
Object.assign(app, {
    // --- FORM & TEMPLATE HELPERS ---
    getNestedValue(obj, path) {
        return path.split('.').reduce((o, k) => (o && o[k] !== undefined) ? o[k] : null, obj);
    },

    setNestedValue(path, value, isNumber = false, baseObj = this.state) {
        const keys = path.split('.');
        let obj = baseObj;
        for (let i = 0; i < keys.length - 1; i++) {
            if (!obj[keys[i]]) {
                obj[keys[i]] = {};
            }
            obj = obj[keys[i]];
        }
        obj[keys[keys.length - 1]] = isNumber ? parseFloat(value) || 0 : value;
    },
    
    createEmptySheet(template) {
        const sheet = {};
        template.forEach(section => {
            section.fields.forEach(field => {
                this.setNestedValue(field.id, field.type === 'tags' ? [] : (field.type === 'number' ? 0 : ''), false, sheet);
            });
        });
        return sheet;
    },

    // --- IMPORT / EXPORT (Local Fallback) ---
    exportSession() {
        this.exportJson(this.state, `dnd-session-${new Date().toISOString()}.json`);
    },

    importSession(event) {
        this.importJson(event, (data) => {
            try {
                if (data.agents && data.chatHistory) {
                    this.state = data;
                    this.render();
                    alert('Local session imported successfully! Note: This does not save to the backend.');
                } else { throw new Error('Invalid session file format.'); }
            } catch (error) { alert('Error importing session: ' + error.message); }
        });
        event.target.value = '';
    },

    exportProfile() { 
        this.exportJson(this.state.userProfile, 'user-profile.json'); 
    },
    
    importProfile(event) { 
        this.importJson(event, (data) => {
            try {
                this.state.userProfile = data;
                this.renderProfile();
                alert('Profile imported successfully!');
            } catch (error) { 
                alert('Error importing profile: ' + error.message); 
            }
        });
        event.target.value = '';
    },
    
    exportAgent(agentId) { 
        const agent = this.state.agents.find(a => a.id === agentId);
        if (agent) {
            this.exportJson(agent, `agent-${agent.name.replace(/\s+/g, '-').toLowerCase()}.json`);
        }
    },
    
    importAgent(event, agentId) { 
        this.importJson(event, (data) => {
            try {
                const agentIndex = this.state.agents.findIndex(a => a.id === agentId);
                if (agentIndex !== -1) {
                    // Keep the original ID but update everything else
                    data.id = agentId;
                    this.state.agents[agentIndex] = data;
                    this.renderAgents();
                    alert('Agent imported successfully!');
                }
            } catch (error) { 
                alert('Error importing agent: ' + error.message); 
            }
        });
        event.target.value = '';
    },

    exportJson(data, filename) {
        const dataStr = JSON.stringify(data, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', filename);
        linkElement.click();
    },

    importJson(event, callback) {
        const file = event.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = JSON.parse(e.target.result);
                callback(data);
            } catch (error) { alert('Error parsing JSON file: ' + error.message); }
        };
        reader.readAsText(file);
        event.target.value = '';
    }
});