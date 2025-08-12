// ===================================================================================
// --- BACKEND INTEGRATION: API Service Layer ---
// This object centralizes all communication with the backend.
// ===================================================================================
const apiService = {
    /**
     * Loads the entire session state from the backend.
     * @returns {Promise<object|null>} A promise that resolves with the full application state object, or null if no session exists.
     */
    async loadSession() {
        console.log("BACKEND CALL (MOCK): Loading session...");
        // ** REAL IMPLEMENTATION: **
        // const response = await fetch('/api/session');
        // if (response.ok) {
        //     return await response.json();
        // }
        // return null;

        // ** MOCK IMPLEMENTATION: **
        // For now, we return null to allow the app to create a default new session.
        // To test loading, you can return a mock state object here.
        return null; 
    },

    /**
     * Sends the current context to the backend LLM and gets a response.
     * @param {object} payload - The data to send to the LLM.
     * @param {Array} payload.chatHistory - The full chat history.
     * @param {Array} payload.agents - All agent configurations.
     * @param {object} payload.userProfile - The user's profile data.
     * @param {object} payload.settings - The current AI settings (temp, etc.).
     * @returns {Promise<object>} A promise that resolves with the AI's response.
     * The response should include the new message and any updated agent stats.
     */
    async getLlmResponse(payload) {
        console.log("BACKEND CALL: Getting LLM response for payload:", payload);
        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            return data;
        } catch (error) {
            console.error("Error calling LLM API:", error);
            // Fallback response for error cases
            return {
                newMessage: {
                    sender: "System",
                    text: `Error: ${error.message}. Please check the console for details.`
                },
                updatedAgentId: payload.agents.find(a => a.isDM)?.id || "agent-dm",
                usageStats: {
                    tokensUsed: 0,
                    price: 0
                }
            };
        }
    },

    /**
     * Saves a single object (like an agent or note) to the backend.
     * This is an example of a more granular save operation.
     * @param {string} type - The type of data being saved (e.g., 'agent', 'note').
     * @param {object} data - The data object to save.
     * @returns {Promise<object>} A promise that resolves with the saved data, possibly including a backend-generated ID.
     */
    async saveData(type, data) {
        console.log(`BACKEND CALL (MOCK): Saving ${type}`, data);
        // ** REAL IMPLEMENTATION: **
        // const response = await fetch(`/api/${type}`, {
        //     method: data.id ? 'PUT' : 'POST', // PUT to update, POST to create
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify(data)
        // });
        // return await response.json();

        // ** MOCK IMPLEMENTATION: **
        // Return the same data, adding a mock ID if it's new.
        if (!data.id) {
            data.id = `${type}-${Date.now()}`;
        }
        return data;
    },

    /**
     * Deletes a single object from the backend.
     * @param {string} type - The type of data being deleted (e.g., 'agent', 'note').
     * @param {string} id - The ID of the object to delete.
     * @returns {Promise<void>}
     */
    async deleteData(type, id) {
        console.log(`BACKEND CALL (MOCK): Deleting ${type} with id ${id}`);
        // ** REAL IMPLEMENTATION: **
        // await fetch(`/api/${type}/${id}`, { method: 'DELETE' });
        
        // ** MOCK IMPLEMENTATION: **
        return Promise.resolve();
    },
    
    /**
     * Saves a settings object.
     * @param {object} settings - The settings object.
     * @returns {Promise<void>}
     */
     async saveSettings(settings) {
        console.log("BACKEND CALL (MOCK): Saving settings", settings);
        // ** REAL IMPLEMENTATION: **
        // await fetch('/api/settings', {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify(settings)
        // });
     }
};