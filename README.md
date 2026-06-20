# MiniERP — Flask + PyInstaller

## Folder Structure
```
erp_app/
├── app.py                  # Entry point
├── erp.spec                # PyInstaller packaging config
├── requirements.txt
├── erp.db                  # Created automatically on first run
├── modules/
│   ├── db.py               # SQLite init + connection
│   ├── hr.py               # HR blueprint
│   ├── projects.py         # Projects blueprint
│   ├── timesheet.py        # Timesheet blueprint
│   ├── salary.py           # Salary + statutory calc
│   └── biometric.py        # ESSL sync + manual punch
└── templates/
    ├── base.html
    ├── hr.html
    ├── projects.html
    ├── project_detail.html
    ├── timesheet.html
    ├── salary.html
    └── biometric.html
```

## 1. First-time Setup
```bash
cd erp_app
pip install -r requirements.txt
```

## 2. Run in Development
```bash
python app.py
```
Browser opens automatically at http://127.0.0.1:5000

## 3. Package as Windows .exe
```bash
pip install pyinstaller
pyinstaller erp.spec
```
Output: `dist/MiniERP.exe`  
Double-click to launch — no Python needed on target machine.  
`erp.db` is created next to the .exe on first run.

## 4. ESSL Biometric Sync
- Device must be on the same LAN as the PC running MiniERP
- Default IP: 192.168.1.101, Port: 4370
- Go to Biometric → enter device IP → click "Pull from Device"
- Requires: `pip install pyzk`
- Supported devices: eSSL MB20, iClock series, and most ZKTeco-compatible devices

## 5. Salary Calculations (Indian Statutory)
| Component       | Basis                              |
|-----------------|------------------------------------|
| Basic           | 50% of gross                       |
| HRA             | 20% of gross                       |
| Special Allow.  | Remaining (gross − basic − HRA)    |
| PF (employee)   | 12% of basic, capped at ₹15,000/mo |
| ESI             | 0.75% of gross (if gross ≤ ₹21k)  |
| Professional Tax| ₹200/mo (Maharashtra flat rate)    |
| TDS             | Estimated at 10% above ₹2.5L/yr   |

## 6. Modules Summary
| Module     | Features                                                   |
|------------|------------------------------------------------------------|
| HR         | Add/search/delete employees, PF/ESI flags, PAN validation  |
| Projects   | Create projects, milestones, team assignment, budget track |
| Timesheet  | Weekly grid, log hours by project, navigate weeks          |
| Salary     | Month/year selector, full earnings + deductions slip       |
| Biometric  | ESSL device pull, manual punch entry, daily attendance log |

## 7. Upcoming (Phase 2)
- [ ] PDF payslip export (reportlab)
- [ ] Excel export for payroll register
- [ ] Leave management module
- [ ] Role-based login (Flask-Login)
- [ ] Auto monthly payroll run
- [ ] WhatsApp payslip dispatch (same as housing society app)
