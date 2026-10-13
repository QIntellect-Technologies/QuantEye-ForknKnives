import json

# Mock DB rows
_allLeaveRequests = [
    {'id': 1, 'user_id': 1, 'status': 'pending'},
    {'id': 2, 'user_id': 1, 'status': 'approved'},
    {'id': 3, 'user_id': 2, 'status': 'rejected'},
    {'id': 4, 'user_id': 2, 'status': 'partially_approved'},
]

def getLeaveStatusEntries(req, statusFilter):
    status = statusFilter.lower()
    if status == 'all':
        return [req]
    if req.get('status', '').lower() == status:
        return [req]
    return []

def filterLeavesTable(statusFilter):
    filtered = []
    for req in _allLeaveRequests:
        statusMatch = len(getLeaveStatusEntries(req, statusFilter)) > 0
        if statusMatch:
            filtered.append(req)
            
    filteredGroups = [{'user_id': r['user_id'], 'requests': [r]} for r in filtered]
    
    total = len(filteredGroups)
    
    totalStatusLeaveCount = sum(len(getLeaveStatusEntries(req, statusFilter)) for req in filtered)
    
    # Assuming page 1, size 25
    pagedGroups = filteredGroups
    pageStatusLeaveCount = sum(
        sum(len(getLeaveStatusEntries(req, statusFilter)) for req in group['requests']) 
        for group in pagedGroups
    )
    
    print(f"Filter: {statusFilter}")
    print(f"total: {total}")
    print(f"filtered length: {len(filtered)}")
    print(f"totalStatusLeaveCount: {totalStatusLeaveCount}")
    print(f"pageStatusLeaveCount: {pageStatusLeaveCount}")
    print("-" * 30)

filterLeavesTable('all')
filterLeavesTable('pending')
filterLeavesTable('approved')
filterLeavesTable('partially_approved')
