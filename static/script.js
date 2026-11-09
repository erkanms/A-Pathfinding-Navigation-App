document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('resolve_address');
    const results = document.getElementById('results');
    const nodes = document.getElementById('nodes');
    const map = document.getElementById("map");
    const overlay = document.getElementById('loading_overlay');
    const reset = document.getElementById('reset');
    const request_route = document.getElementById('request_route');
    const nodepath = document.getElementById('route')

    async function request_basemap() {
        try {
            const response = await fetch('/api/basemap', {
                method: 'GET'
            });

            if (!response.ok) throw new Error(`HTTP ${response.status} ${response.statusText}`);

            const basemap = await response.text();


            const iframe = document.createElement('iframe')
            iframe.srcdoc = basemap;
            iframe.width = '100%'
            iframe.height = '100%';
            iframe.style.display = 'block';
            iframe.style.pointerEvents = 'auto';
            iframe.tabIndex = 0;

            iframe.addEventListener('load', () => {
            try { iframe.contentWindow.focus(); } catch (err) { console.warn('iframe focus failed', err); }
            console.log('iframe loaded');
        });

        if (!map) {
            console.error('map element not found; cannot append iframe');
            return;
        }
        map.innerHTML = '';
        map.appendChild(iframe);
        console.log('iframe appended');

        }
        catch (e) {
            console.error(e);
            if (map) map.innerHTML = `<div class="error">Error: ${escapeHtml(e.message)}</div>`;
        }
    };

    request_basemap()

    if (!form) console.error('No <form> element found on the page.');

    async function search(event) {
        event.preventDefault(); // stop page reload / default submit

        const formData = new FormData(form);
        console.log(...formData); // optional - inspect submitted pairs

        try {
            const response = await fetch('/api/forward', {
                method: 'POST',
                body: formData // send multipart/form-data; change if your API expects JSON
            });

            if (!response.ok) throw new Error(`HTTP ${response.status} ${response.statusText}`);

            // parse JSON response
            const items = await response.json();

            results.innerHTML = ''; // Clear previous contents

            // normalize response into an array
            let list;
            if (Array.isArray(items)) {
                list = items;
            } else if (items && Array.isArray(items.items)) {
                list = items.items;
            } else if (items && Array.isArray(items.results)) {
                list = items.results;
            } else if (items && (items.display_name || items.name || items.lat || items.lon)) {
                list = [items];
            } else {
                list = [];
            }

            if (list.length === 0) {
                results.innerHTML = '<div class="info">No results returned.</div>';
                return;
            }

            // render each result; keep latitude and longitude separate
            list.forEach((item, index) => {
                const name = item.display_name || item.name || item.title || '';
                // common keys: Nominatim -> lat, lon (strings)
                const lat = item.lat ?? item.latitude ?? (item.location && item.location.lat) ?? '';
                const lon = item.lon ?? item.longitude ?? (item.location && item.location.lon) ?? '';

                const div = document.createElement('div');
                div.id = `section-${index}`;
                div.classList.add('item');
                div.innerHTML = `
                    <strong id="name-${index}">${escapeHtml(name)}</strong>
                    <div id="coords-${index}" class="coords">
                        <span class="lat"><em>${escapeHtml(lat)}</em></span>
                        <span class="lon"><em>${escapeHtml(lon)}</em></span>
                    </div>
                    <pre class="raw">${escapeHtml(JSON.stringify(item, null, 2))}</pre>
                    <button id="select_address-${index}" type="button" class="select-btn">Select</button>
                `;
                results.appendChild(div);
            });

        } catch (e) {
            console.error(e);
            if (results) results.innerHTML = `<div class="error">Error: ${escapeHtml(e.message)}</div>`;
        }
    };

    async function get_route() {
    const start = globalThis.START;
    const end = globalThis.END;

    overlay.classList.add('active');
    overlay.style.display = 'flex';

    try {
        const response = await fetch('/api/route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start, end })
        });
        if (!response.ok) throw new Error(`HTTP ${response.status} ${response.statusText}`);
        const route = await response.json();

        overlay.classList.remove('active');
        overlay.style.display = 'none';

        const iframe = document.createElement('iframe')
        iframe.srcdoc = route['route'];
        iframe.style.width = '100%';
        iframe.style.height = '100%';
        iframe.style.border = 'none';
        iframe.style.display = 'block';
        iframe.tabIndex = 0;

        let list = route['directions'];
        nodepath.innerHTML = '<h3>Directions</h3>'; // Clear previous
        list.forEach((item, index) => {
            const div = document.createElement('div');
            div.id = `node-${index}`;
            div.classList.add('item');
            div.innerHTML = `<strong>${escapeHtml(item)}</strong>`;
            nodepath.appendChild(div);
        });

        map.innerHTML = '';
        map.appendChild(iframe);

    } catch (e) {
        console.error(e);
        overlay.classList.remove('active');
        overlay.style.display = 'none';
        if (map) map.innerHTML = `<div class="error">Error: ${escapeHtml(e.message)}</div>`;
    }
};

    function select_address(buttonId) {
    // extract numeric index from id like "select_address-3"
    const idx = String(buttonId).split('-').pop();

    // read the name element by its id
    const nameEl = document.getElementById(`name-${idx}`);
    const name = nameEl ? nameEl.textContent.trim() : '';

    // select the coords element by its id
    const coordsEl = document.getElementById(`coords-${idx}`);
    if (!coordsEl) {
        console.warn('coords element not found for index', idx);
        return;
    }

    // read latitude and longitude separately (use textContent, not innerHTML())
    const lat = coordsEl.querySelector('.lat em')?.textContent.trim() || '';
    const lon = coordsEl.querySelector('.lon em')?.textContent.trim() || '';

    if (typeof globalThis.START === 'undefined') {
        globalThis.START = { name, lat, lon };
        results.innerHTML = '';
        const span = document.createElement('span');
        const start = globalThis.START;

        span.id = "start_node";
        span.classList.add('start');
        span.innerHTML = `
            <h3> Start Node </h3>
            <strong id="start-name">${start.name}</strong>
        `;
        nodes.appendChild(span);
        
        reset.style.display = 'inline';
        form.reset();


    } else if(typeof globalThis.END === 'undefined') {
        globalThis.END = { name, lat, lon };
        const end = globalThis.END;
        const span = document.createElement('span');
        results.innerHTML='';
        span.id = "end_node";
        span.classList.add('end');
        span.innerHTML = `
            <h3> End Node </h3>
            <strong id="start-name">${end.name}</strong>
        `;
        nodes.appendChild(span);
        
        request_route.style.display = 'inline';
        form.reset();
    } else {
        results.innerHTML-'';
        results.innerHTML = `
            <div class='error'>Start and End Node already selected, reset to change search queries.</div>
        `;    
    }


    console.log('selected index:', idx, 'lat:', lat, 'lon:', lon);
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str).replace(/[&<>"']/g, s => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[s]));
    }
    // attach listener
    form.addEventListener('submit', search);
    console.log('submit listener attached');

    results.addEventListener('click', (e) => {
        const btn = e.target.closest('button.select-btn'); // find nearest .select-btn
        if (!btn) return; // ignore clicks that are not on a select button
        e.preventDefault();
        const id = btn.id; // id of the button that initiated the event
        console.log('selected button id:', id);
        select_address(id); // call your handler with id (and element if needed
    });
    request_route.addEventListener('click', get_route) 
});



