// One realm token per iframe load. Streamlit injects this script inside an
// iframe and destroys that iframe whenever the element it belongs to is
// remounted. The listeners registered from it stay attached to elements that
// live in the parent document, but they belong to a torn-down realm and never
// fire again, so a guard that only asks "is something attached?" leaves the
// slash menu permanently dead. Comparing tokens instead re-attaches whenever
// this script is running in a realm the element has not seen.
const REALM = "realm-" + Math.random().toString(36).slice(2);

const init = function(commands) {
    const doc = window.parent.document || document;

    const labelSteppers = () => {
        doc.querySelectorAll('button[data-testid=stNumberInputStepDown]').forEach(b => b.setAttribute('aria-label', 'Decrease'));
        doc.querySelectorAll('button[data-testid=stNumberInputStepUp]').forEach(b => b.setAttribute('aria-label', 'Increase'));
    };

    const nameLandmarks = () => {
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
    };

    // Building the menu with `var(...)` rather than literal colours: the
    // palette is declared once in the stylesheets, and a menu built from
    // copies of it goes stale the moment a theme value changes.
    const buildMenu = (chatInput) => {
        const menu = doc.createElement('div');
        menu.id = 'slash-commands-menu';
        // Fixed and anchored to the body rather than absolute inside the chat
        // input: that container is React's, so anything appended to it is
        // destroyed on the next render, and it sits inside a column that can
        // clip or stack over the menu. Coordinates are computed from the input
        // each time the menu opens.
        menu.style.cssText = [
            'position: fixed',
            'background-color: var(--bg-surface)',
            'border: 1px solid var(--border-subtle)',
            'border-radius: 12px',
            'box-shadow: var(--shadow-lg)',
            'z-index: 2147483647',
            'margin-bottom: 8px',
            'display: none',
            'padding: 8px 0',
            'box-sizing: border-box',
            "font-family: var(--font-family)"
        ].join(';');

        commands.forEach((c) => {
            const item = doc.createElement('div');
            item.style.cssText = [
                'padding: 8px 16px',
                'cursor: pointer',
                'display: flex',
                'justify-content: space-between',
                'align-items: center',
                'color: var(--text-primary)',
                'font-size: 0.9rem',
                'transition: background-color 0.2s'
            ].join(';');

            item.innerHTML =
                '<div><strong style="color: var(--accent-primary)">' + c.cmd + '</strong>' +
                '<span style="margin-left: 8px; color: var(--text-secondary)">' + c.desc + '</span></div>' +
                '<span style="font-size: 0.75rem; background-color: var(--bg-elevated); padding: 2px 6px;' +
                ' border-radius: 4px; color: var(--accent-primary)">Cmd</span>';

            item.addEventListener('mouseenter', () => { item.style.backgroundColor = 'var(--bg-elevated)'; });
            item.addEventListener('mouseleave', () => { item.style.backgroundColor = 'transparent'; });

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

        doc.body.appendChild(menu);
        return menu;
    };

    const attachSlashMenu = () => {
        const chatInput = doc.querySelector('[data-testid=stChatInput] textarea');
        if (!chatInput || chatInput.dataset.slashMenuRealm === REALM) {
            return;
        }
        chatInput.dataset.slashMenuRealm = REALM;

        // Clearing whatever the previous realm left behind, so its dead
        // listeners and its menu do not pile up on top of the live ones.
        const stale = doc.getElementById('slash-commands-menu');
        if (stale) stale.remove();

        const previous = window.parent.slashMenuListeners;
        if (previous) {
            previous.input.removeEventListener('input', previous.onType);
            previous.input.removeEventListener('keyup', previous.onType);
            doc.removeEventListener('click', previous.onClickAway);
        }

        const menu = buildMenu(chatInput);

        const placeMenu = () => {
            // Measuring the visible input box, not the textarea inside it, so
            // the menu lines up with what the operator sees.
            const anchor = chatInput.closest('[data-testid=stChatInput]') || chatInput;
            const box = anchor.getBoundingClientRect();
            menu.style.left = box.left + 'px';
            menu.style.width = box.width + 'px';
            menu.style.bottom = (doc.defaultView.innerHeight - box.top + 8) + 'px';
        };

        const onType = (e) => {
            const val = e.target.value;
            if (val === '/') {
                placeMenu();
                menu.style.display = 'block';
            } else if (!val.startsWith('/')) {
                menu.style.display = 'none';
            }
        };

        const onClickAway = (e) => {
            if (!menu.contains(e.target) && e.target !== chatInput) {
                menu.style.display = 'none';
            }
        };

        chatInput.addEventListener('input', onType);
        chatInput.addEventListener('keyup', onType);
        doc.addEventListener('click', onClickAway);

        window.parent.slashMenuListeners = { input: chatInput, onType: onType, onClickAway: onClickAway };
    };

    const fix = () => {
        labelSteppers();
        nameLandmarks();
        attachSlashMenu();
    };

    fix();

    // Polling from this realm only. A previous realm's interval died with the
    // iframe that owned it, so there is nothing to clear and no risk of two
    // running at once.
    setInterval(fix, 1000);
};

if (window.parent) {
    window.parent.initAccessibility = init;
}
window.initAccessibility = init;
