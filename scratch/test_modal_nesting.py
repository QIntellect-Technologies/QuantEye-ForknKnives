from bs4 import BeautifulSoup

with open('templates/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = """        <button type="button" class="btn btn-secondary" onclick="closeCameraModal()">Cancel</button>
        <button type="button" class="btn btn-primary" onclick="saveCameraConfig()" style="background:#3d9fd4; border:none; font-weight:700;">Save Camera Configuration</button>
      </div>
    </div>
  <!-- File Leave Request Modal -->"""

replacement = """        <button type="button" class="btn btn-secondary" onclick="closeCameraModal()">Cancel</button>
        <button type="button" class="btn btn-primary" onclick="saveCameraConfig()" style="background:#3d9fd4; border:none; font-weight:700;">Save Camera Configuration</button>
      </div>
    </div>
  </div>

  <!-- File Leave Request Modal -->"""

if target in text:
    fixed = text.replace(target, replacement)
    soup = BeautifulSoup(fixed, 'html.parser')
    modals = [
        'deptModal', 'desigModal', 'cameraModal', 'fileLeaveModal',
        'addOvertimeModal', 'leaveTypeModal', 'companyHolidayModal',
        'editSalaryConfigModal', 'autoOtRateModal', 'adminPasswordModal'
    ]
    for m in modals:
        el = soup.find(id=m)
        if el:
            parent = el.parent.get('id') or el.parent.name
            print(f'{m}: parent = {parent}')
else:
    print("Target not found in text!")
