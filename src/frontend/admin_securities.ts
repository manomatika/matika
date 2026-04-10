import { MaintenanceActivityManager, ActivityMetadata } from './maintenance_activity.js';
import { LookupDialog, LookupResult } from './lookup_dialog.js';

class SecuritiesManager extends MaintenanceActivityManager {
    private lookupDialog: LookupDialog;
    private btnBulkAdd = document.getElementById('btn-bulk-add') as HTMLElement;
    private btnBulkDelete = document.getElementById('btn-bulk-delete') as HTMLElement;

    constructor(metadata: ActivityMetadata) {
        super(metadata);
        this.lookupDialog = new LookupDialog();
        this.initSecuritiesListeners();
    }

    private initSecuritiesListeners() {
        const lookupButtons = document.querySelectorAll('.btn-lookup');
        lookupButtons.forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const symbolInput = document.getElementById('field-symbol') as HTMLInputElement;
                const results = await this.lookupDialog.open({
                    title: "Symbol Lookup", 
                    multiSelect: false, 
                    initialValue: symbolInput.value
                });
                if (results && results.length > 0) {
                    this.fetchMetadata(results[0].symbol);
                }
            });
        });

        this.btnBulkAdd?.addEventListener('click', () => this.handleBulkAdd());
        this.btnBulkDelete?.addEventListener('click', () => this.handleBulkDelete());

        const refreshButtons = document.querySelectorAll('.btn-refresh-field');
        refreshButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.refreshPrice();
            });
        });
    }

    protected override selectRow(row: HTMLElement) {
        super.selectRow(row);
        if (this.selectedRow) {
            this.refreshPrice(true);
        }
    }

    private async refreshPrice(silent: boolean = false) {
        const symbolInput = document.getElementById('field-symbol') as HTMLInputElement;
        const symbol = symbolInput?.value;
        if (!symbol) return;

        try {
            if (!silent) this.showMessage(`Refreshing price for ${symbol}...`);
            const resp = await fetch(`/admin/securities/lookup?symbol=${encodeURIComponent(symbol)}`);
            if (resp.ok) {
                const data = await resp.json();
                const priceInput = document.getElementById('field-current_price') as HTMLInputElement;
                if (priceInput && data.current_price) {
                    priceInput.value = data.current_price;
                    if (!silent) this.showMessage(`Updated price for ${symbol}: ${data.current_price}`);
                    this.checkDirty();
                }
            }
        } catch (err) {
            if (!silent) this.showMessage(`Failed to refresh price for ${symbol}`, true);
        }
    }

    private async handleBulkAdd() {
        const results = await this.lookupDialog.open({
            title: "Bulk Add", 
            multiSelect: true
        });
        if (results && results.length > 0) {
            this.showMessage(`Adding ${results.length} securities...`);
            const symbols = results.map(r => r.symbol);
            try {
                const resp = await fetch('/admin/securities/bulk_create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbols })
                });

                if (resp.ok) {
                    window.location.href = `/admin/securities?select=${symbols[0]}`;
                } else {
                    const data = await resp.json();
                    this.showMessage(data.detail || "Bulk add failed", true);
                }
            } catch (err: any) {
                this.showMessage(err.message || "An error occurred during bulk add", true);
            }
        }
    }

    private async handleBulkDelete() {
        // (3) Implement Bulk Delete
        const allSecurities: LookupResult[] = [];
        const rows = document.querySelectorAll('#browse-table tbody tr');
        rows.forEach(row => {
            const cells = (row as HTMLTableRowElement).cells;
            if (cells.length >= 2) {
                allSecurities.push({
                    symbol: cells[0].textContent?.trim() || '',
                    name: cells[1].textContent?.trim() || ''
                });
            }
        });

        const results = await this.lookupDialog.open({
            title: "Bulk Delete",
            multiSelect: true,
            defaultChecked: false,
            statusTemplate: "{N} records selected to be deleted",
            preloadedResults: allSecurities
        });

        if (results && results.length > 0) {
            if (!confirm(`Are you sure you want to delete ${results.length} securities?`)) return;
            
            this.showMessage(`Deleting ${results.length} securities...`);
            const symbols = results.map(r => r.symbol);
            try {
                const resp = await fetch('/admin/securities/bulk_delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbols })
                });

                if (resp.ok) {
                    window.location.reload();
                } else {
                    const data = await resp.json();
                    this.showMessage(data.detail || "Bulk delete failed", true);
                }
            } catch (err: any) {
                this.showMessage(err.message || "An error occurred during bulk delete", true);
            }
        }
    }

    private async fetchMetadata(symbol: string) {
        try {
            this.showMessage(`Fetching metadata for ${symbol}...`);
            const resp = await fetch(`/admin/securities/lookup?symbol=${encodeURIComponent(symbol)}`);
            if (!resp.ok) {
                if (resp.status === 404) {
                    throw new Error(`Security details for '${symbol}' not found.`);
                }
                throw new Error(`Lookup failed with status ${resp.status}`);
            }
            const data = await resp.json();
            this.populateFormWithMetadata(data);
            this.showMessage(`Successfully loaded ${symbol}`);
        } catch (err: any) {
            this.showMessage(err.message || "Error fetching security metadata.", true);
        }
    }

    private populateFormWithMetadata(data: any) {
        const mapping: Record<string, any> = {
            'symbol': data.symbol,
            'name': data.name,
            'security_type': data.security_type,
            'asset_class': data.asset_class,
            'previous_close': data.previous_close,
            'open_price': data.open_price,
            'current_price': data.current_price,
            'nav': data.nav,
            'range_52_week': data.range_52_week,
            'avg_volume': data.avg_volume,
            'yield_30_day': data.yield_30_day,
            'yield_7_day': data.yield_7_day
        };

        Object.keys(mapping).forEach(key => {
            const input = document.getElementById(`field-${key}`) as HTMLInputElement | HTMLSelectElement;
            if (input && mapping[key] !== undefined) {
                if (key.startsWith('yield_') && mapping[key]) {
                    const num = parseFloat(mapping[key]);
                    if (!isNaN(num)) {
                        input.value = (num * 100).toFixed(2) + '%';
                    } else {
                        input.value = mapping[key];
                    }
                } else {
                    input.value = mapping[key] || '';
                }
            }
        });
        
        this.checkDirty();
    }

    protected override getCreateUrl() { return "/admin/securities/create"; }
    protected override getUpdateUrl(id: string) { return `/admin/securities/update/${id}`; }
    protected override getDeleteUrl(id: string) { return `/admin/securities/delete/${id}`; }
}

document.addEventListener('DOMContentLoaded', () => {
    const metadataElement = document.getElementById('metadata-json');
    if (metadataElement) {
        const metadata = JSON.parse(metadataElement.textContent || '{}');
        const manager = new SecuritiesManager(metadata);

        const urlParams = new URLSearchParams(window.location.search);
        const selectSymbol = urlParams.get('select');
        if (selectSymbol) {
            const rows = document.querySelectorAll('#browse-table tbody tr');
            for (const row of rows) {
                const symbolCell = (row as HTMLTableRowElement).cells[0];
                if (symbolCell && symbolCell.textContent?.trim().toUpperCase() === selectSymbol.toUpperCase()) {
                    (row as HTMLElement).click();
                    break;
                }
            }
        }
    }
});
