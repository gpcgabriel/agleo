const init = function(isDark, commands) {
    const doc = window.parent.document || document;
    
    const fix = () => {
        doc.querySelectorAll('button[data-testid=stNumberInputStepDown]').forEach(b => b.setAttribute('aria-label', 'Decrease'));
        doc.querySelectorAll('button[data-testid=stNumberInputStepUp]').forEach(b => b.setAttribute('aria-label', 'Increase'));
        
        const sb = doc.querySelector('[data-testid=stSidebar]');
        if (sb) {
            sb.setAttribute('role', 'region');
            sb.setAttribute('aria-label', 'Sidebar Menu');
        }
        
        const mc = doc.querySelector('.block-container');
        if (mc) {
            mc.setAttribute('role', 'main');
            mc.setAttribute('aria-label', 'Main Content');
        }

        // ==========================================
        // BULLETPROOF: "Toggle Sidebar" Button
        // ==========================================
        let sidebarBtn = doc.getElementById('custom-show-sidebar-btn');
        if (!sidebarBtn) {
            sidebarBtn = doc.createElement('button');
            sidebarBtn.id = 'custom-show-sidebar-btn';
            sidebarBtn.innerHTML = '☰ Toggle Sidebar';
            
            // Using cssText with !important prevents Streamlit from hiding or overriding it
            sidebarBtn.style.cssText = `
                position: fixed !important;
                top: 10px !important;
                left: 50% !important;
                transform: translateX(-50%) !important;
                z-index: 9999999 !important;
                padding: 8px 16px !important;
                background-color: ${isDark ? '#1a1b24' : '#ffffff'} !important;
                color: ${isDark ? '#e8eaed' : '#1a1a2e'} !important;
                border: 1px solid ${isDark ? '#2a2b36' : '#e5e5e5'} !important;
                border-radius: 20px !important;
                cursor: pointer !important;
                font-family: 'Inter', sans-serif !important;
                font-size: 13px !important;
                font-weight: 600 !important;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2) !important;
                display: block !important;
                transition: background-color 0.2s !important;
            `;

            // Aggressive click handler to find Streamlit's exact buttons
            sidebarBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();

                // Find the wrapper for the collapsed "open" button
                const expandWrapper = doc.querySelector('[data-testid="collapsedControl"]') || 
                                      doc.querySelector('[data-testid="stSidebarCollapsedControl"]');
                
                // Find the close button inside the sidebar
                const collapseBtn = doc.querySelector('[data-testid="stSidebarCollapseButton"]') || 
                                    doc.querySelector('button[aria-label="Collapse sidebar"]') ||
                                    doc.querySelector('[data-testid="stSidebar"] button');

                // If expand wrapper is visible, click the button inside it
                if (expandWrapper && expandWrapper.offsetParent !== null) {
                    const actualBtn = expandWrapper.querySelector('button') || expandWrapper;
                    actualBtn.click();
                } 
                // Otherwise, close the sidebar
                else if (collapseBtn) {
                    collapseBtn.click();
                }
            });

            sidebarBtn.addEventListener('mouseenter', () => {
                sidebarBtn.style.backgroundColor = isDark ? '#22232e' : '#ececf1';
            });
            sidebarBtn.addEventListener('mouseleave', () => {
                sidebarBtn.style.backgroundColor = isDark ? '#1a1b24' : '#ffffff';
            });

            // Append directly to the highest body element so it's never trapped inside a hidden div
            doc.body.appendChild(sidebarBtn);
        }
        // ==========================================
        
        // Setup Autocomplete Slash Commands Menu
        const chatInput = doc.querySelector('[data-testid=stChatInput] textarea');
        if (chatInput && chatInput.dataset.slashMenuAttached !== 'true') {
            chatInput.dataset.slashMenuAttached = 'true';
            
            let menu = doc.getElementById('slash-commands-menu');
            if (!menu) {
                menu = doc.createElement('div');
                menu.id = 'slash-commands-menu';
                menu.style.position = 'absolute';
                menu.style.bottom = '100%';
                menu.style.left = '16px';
                menu.style.right = '16px';
                menu.style.backgroundColor = isDark ? '#1a1b24' : '#ffffff';
                menu.style.border = isDark ? '1px solid #2a2b36' : '1px solid #e5e5e5';
                menu.style.borderRadius = '12px';
                menu.style.boxShadow = '0 -4px 15px rgba(0, 0, 0, 0.2)';
                menu.style.zIndex = '99999';
                menu.style.marginBottom = '8px';
                menu.style.display = 'none';
                menu.style.padding = '8px 0';
                menu.style.fontFamily = "'Inter', sans-serif";
                
                const container = doc.querySelector('[data-testid=stChatInput]');
                if (container) {
                    container.appendChild(menu);
                }
            }
            
            const updateMenu = () => {
                menu.innerHTML = '';
                commands.forEach((c) => {
                    const item = doc.createElement('div');
                    item.style.padding = '8px 16px';
                    item.style.cursor = 'pointer';
                    item.style.display = 'flex';
                    item.style.justifyContent = 'space-between';
                    item.style.alignItems = 'center';
                    item.style.color = isDark ? '#e8eaed' : '#1a1a2e';
                    item.style.fontSize = '0.9rem';
                    item.style.transition = 'background-color 0.2s';
                    
                    item.innerHTML = '<div><strong style=\'color: ' + (isDark ? '#4fc3f7' : '#0ea5e9') + '\'>' + c.cmd + '</strong><span style=\'margin-left: 8px; color: ' + (isDark ? '#9aa0a6' : '#6e6e80') + '\'>' + c.desc + '</span></div><span style=\'font-size: 0.75rem; background-color: ' + (isDark ? '#22232e' : '#ececf1') + '; padding: 2px 6px; border-radius: 4px; color: ' + (isDark ? '#4fc3f7' : '#0ea5e9') + '\'>Cmd</span>';
                    
                    item.addEventListener('mouseenter', () => {
                        item.style.backgroundColor = isDark ? '#22232e' : '#ececf1';
                    });
                    item.addEventListener('mouseleave', () => {
                        item.style.backgroundColor = 'transparent';
                    });
                    
                    item.addEventListener('click', () => {
                        chatInput.value = c.cmd;
                        chatInput.dispatchEvent(new Event('input', { bubbles: true }));
                        menu.style.display = 'none';
                        chatInput.focus();
                        
                        if (c.autoSubmit) {
                            setTimeout(() => {
                                const sendBtn = doc.querySelector('[data-testid=stChatInput] button');
                                if (sendBtn) sendBtn.click();
                            }, 50);
                        } else {
                            chatInput.setSelectionRange(c.cmd.length, c.cmd.length);
                        }
                    });
                    
                    menu.appendChild(item);
                });
            };
            
            updateMenu();
            
            const checkInput = (val) => {
                if (val === '/') {
                    menu.style.display = 'block';
                } else if (!val.startsWith('/')) {
                    menu.style.display = 'none';
                }
            };
            
            chatInput.addEventListener('input', (e) => {
                checkInput(e.target.value);
            });
            
            chatInput.addEventListener('keyup', (e) => {
                checkInput(e.target.value);
            });
            
            doc.addEventListener('click', (e) => {
                if (!menu.contains(e.target) && e.target !== chatInput) {
                    menu.style.display = 'none';
                }
            });
        }
    };
    fix();
    const targetWin = window.parent || window;
    if (!targetWin.fixA11yInterval) {
        targetWin.fixA11yInterval = setInterval(fix, 1000);
    }
};

if (window.parent) {
    window.parent.initAccessibility = init;
}
window.initAccessibility = init;