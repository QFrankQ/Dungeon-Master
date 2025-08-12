// ===================================================================================
// --- DATA TEMPLATES ---
// ===================================================================================

// Extend app with template methods
Object.assign(app, {
    getDndData() {
        return {
            damageTypes: ["Slashing", "Piercing", "Bludgeoning", "Poison", "Acid", "Fire", "Cold", "Radiant", "Necrotic", "Lightning", "Thunder", "Force", "Psychic"],
            conditionTypes: ["Blinded", "Charmed", "Deafened", "Frightened", "Grappled", "Incapacitated", "Invisible", "Paralyzed", "Petrified", "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious", "Exhaustion"]
        }
    },

    getCharacterSheetTemplate() {
        return [
            { title: "Core Stats", columns: 3, fields: [
                { id: 'name', label: 'Character Name', type: 'text' }, { id: 'class', label: 'Class & Level', type: 'text' }, { id: 'race', label: 'Race', type: 'text' }, { id: 'alignment', label: 'Alignment', type: 'text' }, { id: 'background', label: 'Background', type: 'text' }, { id: 'xp', label: 'Experience Points', type: 'number' },
            ]},
            { title: "Combat", columns: 3, fields: [
                { id: 'ac', label: 'Armor Class', type: 'number' }, { id: 'hp.current', label: 'Current HP', type: 'number' }, { id: 'hp.max', label: 'Max HP', type: 'number' }, { id: 'hp.temp', label: 'Temporary HP', type: 'number' }, { id: 'speed', label: 'Speed (ft)', type: 'number' }, { id: 'initiative', label: 'Initiative', type: 'number' }, { id: 'hit_dice', label: 'Hit Dice', type: 'text' }, { id: 'proficiency_bonus', label: 'Proficiency Bonus', type: 'number' },
            ]},
            { title: "Ability Scores", columns: 3, fields: [
                { id: 'attributes.strength', label: 'Strength', type: 'number' }, { id: 'attributes.dexterity', label: 'Dexterity', type: 'number' }, { id: 'attributes.constitution', label: 'Constitution', type: 'number' }, { id: 'attributes.intelligence', label: 'Intelligence', type: 'number' }, { id: 'attributes.wisdom', label: 'Wisdom', type: 'number' }, { id: 'attributes.charisma', label: 'Charisma', type: 'number' },
            ]},
            { title: "Skills & Saves", columns: 1, fields: [ { id: 'saving_throws', label: 'Saving Throws', type: 'textarea' }, { id: 'skills', label: 'Skills', type: 'textarea' }, ]},
            { title: "Features & Traits", columns: 1, fields: [ { id: 'features', label: 'Features & Traits', type: 'textarea' }, ]},
            { title: "Inventory", columns: 1, fields: [ { id: 'inventory', label: 'Equipment', type: 'textarea' }, ]},
            { title: "Spells", columns: 1, fields: [ { id: 'spells', label: 'Spells & Cantrips', type: 'textarea' }, ]}
        ];
    },

    getStatblockTemplate() {
        return [
            { title: "Meta", columns: 3, fields: [
                { id: 'name', label: 'Name', type: 'text' }, { id: 'meta.size', label: 'Size', type: 'text' }, { id: 'meta.type', label: 'Type', type: 'text' }, { id: 'meta.alignment', label: 'Alignment', type: 'text' },
            ]},
            { title: "Core Stats", columns: 3, fields: [
                { id: 'stats.armor_class.value', label: 'AC', type: 'number' }, { id: 'stats.hit_points.average', label: 'HP (Average)', type: 'number' }, { id: 'stats.hit_points.formula', label: 'HP (Formula)', type: 'text' }, { id: 'stats.speed.walk.value', label: 'Speed (Walk)', type: 'number' }, { id: 'stats.challenge.rating', label: 'CR', type: 'text' }, { id: 'stats.proficiency_bonus', label: 'Proficiency Bonus', type: 'number' },
            ]},
            { title: "Attributes", columns: 3, fields: [
                { id: 'attributes.strength.score', label: 'STR Score', type: 'number' }, { id: 'attributes.dexterity.score', label: 'DEX Score', type: 'number' }, { id: 'attributes.constitution.score', label: 'CON Score', type: 'number' }, { id: 'attributes.intelligence.score', label: 'INT Score', type: 'number' }, { id: 'attributes.wisdom.score', label: 'WIS Score', type: 'number' }, { id: 'attributes.charisma.score', label: 'CHA Score', type: 'number' },
            ]},
            { id: "defenses", title: "Defenses & Senses", columns: 2, fields: [
                { id: 'stats.damage_vulnerabilities', label: 'Damage Vulnerabilities', type: 'tags', options: 'damageTypes' },
                { id: 'stats.damage_resistances', label: 'Damage Resistances', type: 'tags', options: 'damageTypes' },
                { id: 'stats.damage_immunities', label: 'Damage Immunities', type: 'tags', options: 'damageTypes' },
                { id: 'stats.condition_immunities', label: 'Condition Immunities', type: 'tags', options: 'conditionTypes' },
                { id: 'stats.senses.passive_perception', label: 'Passive Perception', type: 'number' },
            ]}
        ];
    },

    // --- FORM BUILDING ---
    buildFormFromTemplate(template, data, basePath) {
        let html = '';
        for (const section of template) {
            html += `<fieldset class="border border-gray-200 dark:border-gray-700 p-3 rounded-lg mb-4"><legend class="px-2 font-semibold text-gray-600 dark:text-gray-400">${section.title}</legend>`;
            html += `<div class="grid grid-cols-1 md:grid-cols-${section.columns || 2} gap-4">`;

            for (const field of section.fields) {
                const value = this.getNestedValue(data, field.id);
                html += '<div>';
                html += `<label class="block text-sm font-medium text-gray-600 dark:text-gray-400">${field.label}</label>`;
                const inputClasses = "w-full p-2 rounded-md bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600";
                switch(field.type) {
                    case 'number':
                        html += `<input type="number" value="${value || 0}" class="${inputClasses}">`;
                        break;
                    case 'textarea':
                        html += `<textarea rows="3" class="${inputClasses}">${value || ''}</textarea>`;
                        break;
                    case 'text':
                    default:
                        html += `<input type="text" value="${value || ''}" class="${inputClasses}">`;
                        break;
                }
                html += '</div>';
            }
            html += '</div></fieldset>';
        }
        return html;
    }
});