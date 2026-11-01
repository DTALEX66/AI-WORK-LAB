# Shared UI Core

## 1. Navigation
- `AppShell`
- `Sidebar`
- `Topbar`
- `Breadcrumb`
- `Tabs`
- `CommandPalette`

## 2. Inputs
- `Button`
- `IconButton`
- `Input`
- `SearchInput`
- `Select`
- `MultiSelect`
- `TagInput`
- `DateRange`

## 3. Data display
- `Card`
- `KPI`
- `Table`
- `List`
- `Tree`
- `Timeline`
- `Graph`
- `Badge`
- `Avatar`
- `Progress`

## 4. Feedback
- `Toast`
- `InlineAlert`
- `EmptyState`
- `LoadingSkeleton`
- `ErrorState`
- `OfflineState`

## 5. Overlays
- `Modal`
- `Drawer`
- `Popover`
- `ContextMenu`
- `Tooltip`
- `ConfirmDialog`

## 6. Workflow / governance
- `ApprovalStep`
- `VersionCompare`
- `ConflictResolver`
- `PermissionGate`
- `AuditEvent`

## 7. Layout
- `PageHeader`
- `Section`
- `SplitPane`
- `ResizablePanel`
- `ResponsiveGrid`

### Shared interaction contract
- Hover: 120ms
- Focus: 2px ring + 2px offset
- Pressed: scale(0.99), 80ms
- Modal: 220ms
- Drawer: 280ms
- Toast: 4s default
- Command palette: `Cmd/Ctrl + K`
- Escape closes the topmost overlay
