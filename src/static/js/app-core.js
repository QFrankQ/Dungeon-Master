// ===================================================================================
// --- FRONTEND APPLICATION LOGIC ---
// ===================================================================================
const app = {
    // --- STATE MANAGEMENT ---
    state: {}, // State will be loaded from backend or defaults

    // --- INITIALIZATION ---
    async init() {
        console.log("Initializing Agent Drive UI...");
        
        // BUG FIX: Define templates BEFORE initializing state that depends on them.
        this.characterSheetTemplate = this.getCharacterSheetTemplate();
        this.statblockTemplate = this.getStatblockTemplate();
        this.dndData = this.getDndData();
        
        // --- BACKEND INTEGRATION ---
        // Attempt to load the session from the backend first.
        let loadedState = await apiService.loadSession();
        
        if (loadedState) {
            this.state = loadedState;
            console.log("Session loaded from backend.");
        } else {
            console.log("No session found on backend, creating new default session.");
            this.state = this.getDefaultState();
        }

        this.switchView('chat');
        this.render();
        this.addEventListeners();
    },
    
    getDefaultState() {
        const defaultState = {
            currentView: 'chat',
            darkMode: false,
            settings: {
                textSize: 16,
                ai: { temperature: 0.7, maxOutput: 2048, priceLimit: 5.00 }
            },
            chatHistory: [{
                sender: 'DM',
                text: 'Welcome to your D&D adventure! I am your Dungeon Master, ready to guide you through epic tales and thrilling combat encounters. What would you like to do first?'
            }],
            userProfile: { notes: [], characterSheet: {} },
            agents: [],
            sessionStats: { totalTokens: 0, requestCount: 0, totalPrice: 0 },
            lastScrollPosition: 0,
            lastModalScrollPosition: 0,
        };
        
        // Create default agents
        const dmAgent = this.createAgentObject({
            id: 'agent-dm', name: 'Dungeon Master', active: true, isDM: true,
            systemPrompt: `You are an impartial AI arbiter responsible for running combat encounters in a tabletop roleplaying game. Your sole function is to resolve combat scenarios according to a strict set of rules provided to you in a vectorized JSON database. You do not influence the narrative, character decisions, or the setup of the encounter itself. Your purpose is to ensure combat is resolved fairly, consistently, and according to the established rules.

### Core Directives

1. **Impartiality is Paramount:** You are a neutral referee. You do not have favorites and apply all rules equally to all combat participants, both Player Characters (PCs) and Non-Player Characters (NPCs).
2. **Rule Adherence:** Your primary directive is to follow the Rules as Written (RAW) found within your database. You must be literal in your interpretation.
3. **Consistency is Key:** Once you make a ruling during a combat encounter, it is final for the duration of that combat. You cannot contradict or change your rulings mid-fight.
4. **Assume Player Knowledge:** You are to assume the players understand the game's core mechanics. Do not explain what a condition like "Prone" means or how to make an attack roll unless explicitly asked to clarify a ruling.

Welcome to the D&D adventure! I am your Dungeon Master, ready to guide you through epic tales and thrilling combat encounters. What would you like to do first?`
        });
        const companionAgent = this.createAgentObject({
            id: 'agent-companion-1', name: 'Elara, the Rogue', active: true,
            systemPrompt: 'You are Elara, a witty and nimble rogue...'
        });
        defaultState.agents.push(dmAgent, companionAgent);
        
        // Create empty character sheet
        defaultState.userProfile.characterSheet = this.createEmptySheet(this.getCharacterSheetTemplate());
        
        return defaultState;
    },
    
    addEventListeners() {
        document.getElementById('ai-temp').addEventListener('input', (e) => {
            e.target.nextElementSibling.textContent = e.target.value;
            this.state.settings.ai.temperature = parseFloat(e.target.value);
            apiService.saveSettings(this.state.settings); // --- BACKEND INTEGRATION ---
        });
        document.getElementById('ai-max-output').addEventListener('input', (e) => {
            this.state.settings.ai.maxOutput = parseInt(e.target.value)
            apiService.saveSettings(this.state.settings); // --- BACKEND INTEGRATION ---
        });
        document.getElementById('ai-price-limit').addEventListener('input', (e) => {
            this.state.settings.ai.priceLimit = parseFloat(e.target.value)
            apiService.saveSettings(this.state.settings); // --- BACKEND INTEGRATION ---
        });
        document.getElementById('chat-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });
    },

    // --- VIEW MANAGEMENT ---
    switchView(viewId) {
        this.state.currentView = viewId;
        document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
        document.getElementById(`${viewId}-view`).classList.remove('hidden');
        this.updateActiveNav();
    },

    updateActiveNav() {
        document.querySelectorAll('.nav-button').forEach(btn => {
            if (btn.dataset.view === this.state.currentView) {
                btn.classList.add('bg-indigo-100', 'dark:bg-indigo-500/20', 'text-indigo-600', 'dark:text-indigo-400');
                btn.classList.remove('text-gray-500', 'dark:text-gray-400');
            } else {
                btn.classList.remove('bg-indigo-100', 'dark:bg-indigo-500/20', 'text-indigo-600', 'dark:text-indigo-400');
                btn.classList.add('text-gray-500', 'dark:text-gray-400', 'hover:bg-gray-100', 'dark:hover:bg-gray-700');
            }
        });
    },

    // --- SETTINGS ---
    toggleDarkMode() {
        this.state.darkMode = !this.state.darkMode;
        this.renderSettings();
        apiService.saveSettings(this.state.settings); // --- BACKEND INTEGRATION ---
    },

    updateTextSize(value) {
        const size = Math.max(12, Math.min(20, parseInt(value) || 16));
        this.state.settings.textSize = size;
        document.documentElement.style.fontSize = size + 'px';
        document.getElementById('text-size-input').value = size;
        apiService.saveSettings(this.state.settings); // --- BACKEND INTEGRATION ---
    }
};