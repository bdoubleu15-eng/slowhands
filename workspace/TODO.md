# SlowHands Development Todo List

## Toolbar Functionality
- [ ] **File Menu**
    - [ ] New File (Ctrl+N): Create a new empty tab
    - [x] Open Folder (Ctrl+Shift+O): implemented
    - [x] Open File (Ctrl+O): implemented
    - [x] Save (Ctrl+S): implemented
    - [x] Save As (Ctrl+Shift+S): implemented (renamed from Save All)    - [ ] Close File: Close current tab
- [ ] **Edit Menu**
    - [ ] Undo (Ctrl+Z): Trigger editor undo
    - [ ] Redo (Ctrl+Y): Trigger editor redo
    - [ ] Copy (Ctrl+C): Trigger editor copy
    - [ ] Paste (Ctrl+V): Trigger editor paste
    - [ ] Find (Ctrl+F): Trigger editor find widget
- [ ] **View Menu**
    - [ ] Toggle Sidebar (Ctrl+B)
    - [ ] Toggle Agent Panel (Ctrl+J)
    - [ ] Zoom In/Out
- [ ] **Help Menu**
    - [ ] Keyboard Shortcuts
    - [ ] Documentation
    - [ ] About

## Frontend Improvements
- [x] Fix Status Bar layout (items stacking)
- [ ] Implement tab context menu (Close, Close Others, Copy Path)
- [ ] Add syntax highlighting for more languages (ensure Monaco workers are loaded)
- [ ] Add "unsaved changes" warning when closing dirty tabs

## Backend/Agent
- [ ] Verify file watching/auto-refresh of file explorer
- [ ] Improve error handling for large file reads
- [ ] Implement "Stop Agent" gracefully

## Electron Integration
- [x] Fix duplicate window launch
- [ ] Verify standard keyboard shortcuts (Copy/Paste) work in menus
