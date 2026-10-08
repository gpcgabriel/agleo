// Fading between the themes instead of swapping them at once. The page takes
// the new palette about a quarter of a second after the toggle is clicked,
// but the map is a fresh iframe that only has its new tiles a second or two
// later. So the click marks the page `theme-switching`, which lets the colours
// fade, and `map-waiting`, which fades the map out; the map fades back in once
// the one drawn in the new theme has its tiles. The stylesheet holds the rules
// both classes turn on.
const THEME_TOGGLE = '[data-testid="stElementContainer"]:has(.theme-toggle-marker) + [data-testid="stElementContainer"] button';
const FOLIUM_MAP = 'iframe[title="streamlit_folium.st_folium"]';
const FADE_MS = 400;
const POLL_MS = 50;
const GIVE_UP_MS = 6000;

const initThemeTransition = function() {
    const doc = window.parent.document || document;
    const root = doc.documentElement;
    let latestSwitch = 0;

    const palette = () => getComputedStyle(root).getPropertyValue('--bg-primary');

    // Treating a map whose document cannot be read as ready, so it is shown
    // rather than kept hidden until the give-up time.
    const tilesLoaded = (frame) => {
        try {
            const tiles = frame.contentDocument.querySelectorAll('img.leaflet-tile');
            return tiles.length > 0 && Array.from(tiles).every((tile) => tile.complete);
        } catch (error) {
            return true;
        }
    };

    const followSwitch = () => {
        const switchId = ++latestSwitch;
        const startedAt = performance.now();
        const oldPalette = palette();
        const oldMap = doc.querySelector(FOLIUM_MAP);
        let paletteChangedAt = null;

        root.classList.add('theme-switching');
        if (oldMap) root.classList.add('map-waiting');

        const watch = () => {
            // Leaving the classes to the switch clicked after this one.
            if (switchId !== latestSwitch) return;

            const elapsed = performance.now() - startedAt;
            if (paletteChangedAt === null && palette() !== oldPalette) paletteChangedAt = elapsed;

            const map = doc.querySelector(FOLIUM_MAP);
            if (map && map !== oldMap && tilesLoaded(map)) root.classList.remove('map-waiting');

            const coloursFaded = paletteChangedAt !== null && elapsed - paletteChangedAt > FADE_MS;
            if (coloursFaded) root.classList.remove('theme-switching');

            if (elapsed > GIVE_UP_MS) {
                root.classList.remove('theme-switching', 'map-waiting');
            } else if (root.classList.contains('theme-switching') || root.classList.contains('map-waiting')) {
                setTimeout(watch, POLL_MS);
            }
        };
        setTimeout(watch, POLL_MS);
    };

    const onClick = (event) => {
        if (event.target.closest && event.target.closest(THEME_TOGGLE)) followSwitch();
    };

    // Replacing the listener a previous realm of this script left on the page,
    // for the same reason the slash menu does in accessibility.js.
    const previous = window.parent.themeSwitchListener;
    if (previous) doc.removeEventListener('click', previous, true);
    doc.addEventListener('click', onClick, true);
    window.parent.themeSwitchListener = onClick;
};
