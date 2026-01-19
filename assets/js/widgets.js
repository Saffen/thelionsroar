// thelionsroar/assets/js/widgets.js

const widgetRenderers = {
    // Ticker widget
    ticker: (w) => {
        if (!w.data) return '';
        return w.data.map(item => `<p class="ticker-msg">${item}</p>`).join('');
    },

    // Navigation/Link widget
    navigation: (w) => {
        if (!w.data) return '';
        return `<ul class="widget-nav-list">` + 
            w.data.map(link => `<li><a href="${link.href}">${link.label}</a></li>`).join('') + 
            `</ul>`;
    },

    // Poll widget (klar til brug når du tilføjer data i YAML)
    poll: (w) => {
        if (!w.data) return '';
        return `<form class="poll-widget"><p>${w.data.question}</p>` +
            w.data.options.map(opt => `<label><input type="radio" name="${w.id}"> ${opt}</label>`).join('<br>') +
            `<br><button type="button" class="btn-small">Stem</button></form>`;
    }
};

async function initWidgets() {
    try {
        const response = await fetch('/api/widgets/config');
        const config = await response.json();
        
        // Find alle zoner (f.eks. article-rail-left)
        document.querySelectorAll('[data-widget-zone]').forEach(zone => {
            const zoneId = zone.getAttribute('data-widget-zone');
            const widgets = config.zones[zoneId];
            
            if (widgets) {
                zone.innerHTML = ''; // Ryd "Loading..."
                widgets.forEach(w => {
                    const renderer = widgetRenderers[w.type];
                    if (renderer) {
                        const widgetDiv = document.createElement('div');
                        widgetDiv.className = `widget-card widget-${w.type}`;
                        
                        const titleHtml = `<h3 class="widget-title">${w.title || ''}</h3>`;
                        const contentHtml = `<div id="content-${w.id}">${renderer(w)}</div>`;
                        
                        widgetDiv.innerHTML = titleHtml + contentHtml;
                        zone.appendChild(widgetDiv);
                    }
                });
            }
        });
    } catch (e) {
        console.error("Fejl ved indlæsning af widgets:", e);
    }
}

// Start når siden er klar
document.addEventListener('DOMContentLoaded', initWidgets);