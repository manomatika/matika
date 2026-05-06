export interface ActivityMetadata {
    browse_panel: {
        search_fields?: Array<{
            name: string;
            label_key: string;
        }>;
        columns: Array<{
            name: string;
            label_key: string;
        }>;
    };
    maintenance_panel: {
        buttons: string[];
        fields: Array<{
            name: string;
            label_key: string;
            read_only: boolean;
            required?: boolean;
            type?: string;
            options_source?: string;
            has_lookup?: boolean;
            suffix?: string;
        }>;
    };
}
export declare class MaintenanceActivityManager {
    protected metadata: ActivityMetadata;
    protected selectedRow: HTMLElement | null;
    protected isEditing: boolean;
    protected isNew: boolean;
    protected originalData: Record<string, string>;
    protected btnNew: HTMLButtonElement;
    protected btnEdit: HTMLButtonElement;
    protected btnDelete: HTMLButtonElement;
    protected btnSave: HTMLButtonElement;
    protected btnCancel: HTMLButtonElement;
    protected btnSearch: HTMLButtonElement;
    protected searchInput: HTMLInputElement;
    protected searchField: HTMLSelectElement;
    protected maintenanceForm: HTMLElement;
    protected actionForm: HTMLFormElement;
    protected sep: HTMLElement;
    protected sepContent: HTMLElement;
    constructor(metadata: ActivityMetadata);
    private initEventListeners;
    protected showMessage(msg: string, isError?: boolean): void;
    protected clearMessage(): void;
    protected selectRow(row: HTMLElement): void;
    protected populateFormFromRow(row: HTMLElement): void;
    protected disableForm(): void;
    protected enableForm(): void;
    protected updateButtonStates(): void;
    protected isDirty(): boolean;
    protected checkDirty(): void;
    protected handleNew(): void;
    protected handleEdit(): void;
    protected handleCancel(): void;
    protected handleSave(): Promise<void>;
    protected handleDelete(): Promise<void>;
    protected filterTable(field: string, query: string): void;
    protected getCreateUrl(): string;
    protected getUpdateUrl(id: string): string;
    protected getDeleteUrl(id: string): string;
}
//# sourceMappingURL=maintenance_activity.d.ts.map