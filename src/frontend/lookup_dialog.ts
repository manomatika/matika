export interface LookupResult {
    symbol: string;
    name: string;
    [key: string]: any;
}

export class LookupDialog {
    private modal: HTMLElement;
    private titleElement: HTMLElement;
    private searchInput: HTMLInputElement;
    private btnSearch: HTMLButtonElement;
    private resultsList: HTMLElement;
    private resultsCount: HTMLElement;
    private btnOk: HTMLButtonElement;
    private btnCancel: HTMLButtonElement;
    private statusMessage: HTMLElement;

    private multiSelect: boolean = false;
    private defaultChecked: boolean = true;
    private statusTemplate: string | null = null;
    private selectedSymbols: Set<string> = new Set();
    private currentResults: LookupResult[] = [];
    private resolve: ((value: LookupResult[] | null) => void) | null = null;

    constructor() {
        this.modal = document.getElementById('lookup-modal') as HTMLElement;
        this.titleElement = this.modal.querySelector('.modal-header') as HTMLElement;
        this.searchInput = document.getElementById('lookup-search-input') as HTMLInputElement;
        this.btnSearch = document.getElementById('btn-lookup-search') as HTMLButtonElement;
        this.resultsList = document.getElementById('lookup-results-list') as HTMLElement;
        this.resultsCount = document.getElementById('lookup-results-count') as HTMLElement;
        this.btnOk = document.getElementById('btn-ok-lookup') as HTMLButtonElement;
        this.btnCancel = document.getElementById('btn-close-lookup') as HTMLButtonElement;
        
        // Ensure status message area exists
        this.statusMessage = document.createElement('div');
        this.statusMessage.className = 'lookup-status-message';
        this.statusMessage.style.padding = '0 20px 10px';
        this.statusMessage.style.fontSize = '0.85em';
        this.modal.querySelector('.modal-container')?.insertBefore(this.statusMessage, this.modal.querySelector('.modal-footer'));

        this.initEventListeners();
    }

    private initEventListeners() {
        this.btnSearch.addEventListener('click', () => this.handleSearch());
        this.btnCancel.addEventListener('click', () => this.close(null));
        this.btnOk.addEventListener('click', () => this.handleOk());
        this.searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.handleSearch();
        });
    }

    public open(options: {
        title: string, 
        multiSelect?: boolean, 
        initialValue?: string,
        defaultChecked?: boolean,
        statusTemplate?: string,
        preloadedResults?: LookupResult[]
    }): Promise<LookupResult[] | null> {
        this.titleElement.textContent = options.title;
        this.multiSelect = options.multiSelect || false;
        this.defaultChecked = options.defaultChecked !== undefined ? options.defaultChecked : true;
        this.statusTemplate = options.statusTemplate || null;
        this.searchInput.value = options.initialValue || '';
        this.selectedSymbols.clear();
        this.currentResults = [];
        this.resultsList.innerHTML = '';
        this.resultsCount.textContent = '';
        this.statusMessage.textContent = '';
        this.statusMessage.style.color = '#666';
        this.btnOk.disabled = true;

        if (options.preloadedResults) {
            this.currentResults = options.preloadedResults;
            this.renderResults();
        }

        this.modal.style.display = 'flex';
        this.searchInput.focus();

        return new Promise((resolve) => {
            this.resolve = resolve;
        });
    }

    private async handleSearch() {
        const rawQuery = this.searchInput.value.trim();
        if (!rawQuery) return;

        this.statusMessage.textContent = '';
        this.resultsList.innerHTML = '<tr><td colspan="3" style="padding: 15px;">Searching...</td></tr>';

        let queries: string[] = [];
        if (this.multiSelect) {
            const seen = new Set<string>();
            queries = rawQuery.split(',').map(s => s.trim().toUpperCase()).filter(s => {
                if (!s) return false;
                if (seen.has(s)) return false;
                seen.add(s);
                return true;
            });

            if (queries.length < rawQuery.split(',').length) {
                this.statusMessage.textContent = "Duplicate symbols detected and removed from list.";
                this.statusMessage.style.color = '#c60';
            }
        } else {
            queries = [rawQuery];
        }

        try {
            const allResults: LookupResult[] = [];
            const notFound: string[] = [];

            for (const q of queries) {
                const results = await this.performFetch(q);
                if (results.length > 0) {
                    if (this.multiSelect) {
                        const exact = results.find(r => r.symbol.toUpperCase() === q.toUpperCase());
                        allResults.push(exact || results[0]);
                    } else {
                        allResults.push(...results);
                    }
                } else if (this.multiSelect) {
                    notFound.push(q);
                }
            }

            if (this.multiSelect && notFound.length > 0) {
                const msg = `The following symbols entered: ${notFound.join(', ')} were not found.`;
                this.statusMessage.textContent = msg;
                this.statusMessage.style.color = '#c00';
            }

            this.currentResults = allResults;
            this.renderResults();
        } catch (err: any) {
            this.resultsList.innerHTML = `<tr><td colspan="3" style="padding: 15px; color: #c00;">Error: ${err.message}</td></tr>`;
        }
    }

    private async performFetch(q: string): Promise<LookupResult[]> {
        let resp = await fetch(`/admin/securities/search?q=${encodeURIComponent(q)}`);
        let data = await resp.json();
        
        if (data.length === 0 && !q.endsWith('*')) {
            resp = await fetch(`/admin/securities/search?q=${encodeURIComponent(q + '*')}`);
            data = await resp.json();
        }
        return data;
    }

    private updateStatus() {
        if (this.statusTemplate) {
            this.statusMessage.textContent = this.statusTemplate.replace('{N}', this.selectedSymbols.size.toString());
            this.statusMessage.style.color = '#007bff';
        }
    }

    private renderResults() {
        this.resultsList.innerHTML = '';
        this.resultsCount.textContent = `Found ${this.currentResults.length} record(s)`;
        
        const thead = this.modal.querySelector('thead tr') as HTMLElement;
        if (!thead.querySelector('.cb-col')) {
            const th = document.createElement('th');
            th.className = 'cb-col';
            th.style.width = '30px';
            thead.insertBefore(th, thead.firstChild);
        }
        
        const headerCol = thead.querySelector('.cb-col') as HTMLElement;
        if (this.multiSelect) {
            headerCol.innerHTML = `<input type="checkbox" id="lookup-select-all" ${this.defaultChecked ? 'checked' : ''}>`;
            const selectAll = headerCol.querySelector('#lookup-select-all') as HTMLInputElement;
            selectAll.addEventListener('change', () => {
                const cbs = this.resultsList.querySelectorAll('.row-check') as NodeListOf<HTMLInputElement>;
                cbs.forEach(cb => {
                    cb.checked = selectAll.checked;
                    const symbol = cb.getAttribute('data-symbol')!;
                    if (selectAll.checked) this.selectedSymbols.add(symbol);
                    else this.selectedSymbols.delete(symbol);
                });
                this.btnOk.disabled = this.selectedSymbols.size === 0;
                this.updateStatus();
            });
        } else {
            headerCol.innerHTML = '';
        }

        this.currentResults.forEach((res, index) => {
            const tr = document.createElement('tr');
            tr.className = 'lookup-result-row';
            
            let html = '';
            if (this.multiSelect) {
                const isChecked = this.defaultChecked;
                html += `<td><input type="checkbox" class="row-check" data-symbol="${res.symbol}" ${isChecked ? 'checked' : ''}></td>`;
                if (isChecked) this.selectedSymbols.add(res.symbol);
            } else {
                html += `<td></td>`;
            }
            
            html += `<td><strong>${res.symbol}</strong></td><td>${res.name}</td>`;
            tr.innerHTML = html;

            tr.addEventListener('click', (e) => {
                if (this.multiSelect) {
                    const cb = tr.querySelector('.row-check') as HTMLInputElement;
                    if (e.target !== cb) cb.checked = !cb.checked;
                    if (cb.checked) this.selectedSymbols.add(res.symbol);
                    else this.selectedSymbols.delete(res.symbol);
                } else {
                    this.modal.querySelectorAll('.lookup-result-row').forEach(r => r.classList.remove('selected'));
                    tr.classList.add('selected');
                    this.selectedSymbols.clear();
                    this.selectedSymbols.add(res.symbol);
                }
                this.btnOk.disabled = this.selectedSymbols.size === 0;
                this.updateStatus();
            });

            tr.addEventListener('dblclick', () => {
                this.close([res]);
            });

            this.resultsList.appendChild(tr);
        });

        this.btnOk.disabled = this.selectedSymbols.size === 0;
        this.updateStatus();
    }

    private handleOk() {
        const selected = this.currentResults.filter(r => this.selectedSymbols.has(r.symbol));
        this.close(selected);
    }

    private close(value: LookupResult[] | null) {
        this.modal.style.display = 'none';
        if (this.resolve) this.resolve(value);
    }
}
