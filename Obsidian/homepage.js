//dataviewjs
//1.生成横向的选择栏，包含根目录的文件夹及文件（不包含dataviewjs所在的当前文档）
//2.点击文件夹在下方显示下一级文件夹及文件，点击文件跳转打开
//3.根据窗口自动换行，并保持上下对齐

// 创建文件树结构的函数
function createFileTree() {
    const fileTree = {};
    const currentFilePath = dv.current().file.path;
    
    for (const page of dv.pages('')) {
        if (page.file.path === currentFilePath) continue;
        
        const path = page.file.folder;
        const fileName = page.file.name;
        const fullPath = path ? `${path}/${fileName}` : fileName;
        
        let current = fileTree;
        if (path) {
            path.split('/').forEach(folder => {
                current[folder] = current[folder] || {};
                current = current[folder];
            });
        }
        current[fileName] = {
            isFile: true,
            path: fullPath,
            link: page.file.link
        };
    }
    return fileTree;
}

// 创建DOM元素的函数
function createElement(tag, className = '', text = '') {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text) element.textContent = text;
    return element;
}

// 渲染文件树层级的函数
function renderFileTreeLevel(items, container, level = 0) {
    // 创建水平布局容器
    const horizontalContainer = createElement('div', 'horizontal-container');
    
    // 创建当前层级的内容列表
    const contentList = createElement('div', `content-list content-level-${level}`);
    
    // 排序：文件夹在前，文件在后
    const sortedItems = Object.entries(items).sort(([nameA, dataA], [nameB, dataB]) => {
        const isFileA = dataA.isFile || false;
        const isFileB = dataB.isFile || false;
        if (isFileA !== isFileB) return isFileA ? 1 : -1;
        return nameA.localeCompare(nameB);
    });

    for (const [name, data] of sortedItems) {
        const itemDiv = createElement('div', 'custom-tree-item');
        
        const icon = createElement('span', 'custom-icon', data.isFile ? '📄 ' : '📁 ');
        const nameSpan = createElement('span', 'custom-name', name);
        
        itemDiv.appendChild(icon);
        itemDiv.appendChild(nameSpan);
        
        if (data.isFile) {
            itemDiv.addEventListener('click', (e) => {
                e.stopPropagation();
                const linkPath = data.path.replace(/ /g, '%20');
                app.workspace.openLinkText(linkPath, '', true);
            });
        } else {
            itemDiv.addEventListener('click', (e) => {
                e.stopPropagation();
                
                // 移除所有更高层级的内容
                const nextContainer = itemDiv.closest('.horizontal-container').nextElementSibling;
                if (nextContainer) {
                    nextContainer.remove();
                }
                
                // 创建新的垂直容器
                const verticalContainer = createElement('div', 'vertical-container');
                renderFileTreeLevel(data, verticalContainer, level + 1);
                
                // 将新容器添加到主容器中
                container.appendChild(verticalContainer);
                
                // 更新选中状态
                container.querySelectorAll('.custom-tree-item').forEach(item => {
                    item.classList.remove('custom-selected');
                });
                itemDiv.classList.add('custom-selected');
            });
        }
        
        contentList.appendChild(itemDiv);
    }
    
    horizontalContainer.appendChild(contentList);
    container.appendChild(horizontalContainer);
}

// 添加局部样式
const style = document.createElement('style');
style.textContent = `
    .custom-file-explorer {
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 10px;
        background: var(--background-primary);
        border-radius: 8px;
        margin: 10px 0;
    }
    
    .horizontal-container {
        display: flex;
        flex-direction: column;
        width: 100%;
        margin-bottom: 10px;
    }
    
    .vertical-container {
        margin-top: 10px;
        border-left: 2px solid var(--interactive-accent);
        padding-left: 10px;
    }
    
    .content-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        padding: 10px;
        border: 1px solid var(--background-modifier-border);
        border-radius: 4px;
        width: 100%;
    }
    
    .custom-tree-item {
        display: flex;
        align-items: center;
        padding: 6px 12px;
        cursor: pointer;
        border-radius: 4px;
        background: var(--background-secondary);
        transition: all 0.2s ease;
        min-width: 120px;
        max-width: 200px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .custom-tree-item:hover {
        background: var(--background-modifier-hover);
    }
    
    .custom-tree-item.custom-selected {
        background: var(--interactive-accent);
        color: var(--text-on-accent);
    }
    
    .custom-icon {
        margin-right: 6px;
        flex-shrink: 0;
    }
    
    .custom-name {
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .content-level-0 { background: var(--background-primary); }
    .content-level-1 { background: var(--background-primary-alt); }
    .content-level-2 { background: var(--background-secondary); }
    
    @media (max-width: 768px) {
        .custom-tree-item {
            min-width: 100px;
            max-width: 150px;
        }
    }
`;

// 主容器
const mainContainer = createElement('div', 'custom-file-explorer');
this.container.appendChild(mainContainer);

// 添加样式到容器
const styleContainer = createElement('div');
styleContainer.appendChild(style);
mainContainer.appendChild(styleContainer);

// 创建并渲染文件树
const fileTree = createFileTree();
renderFileTreeLevel(fileTree, mainContainer, 0);
