import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'attendance.db')
if not os.path.exists(DB_PATH):
    # Try current directory
    DB_PATH = 'attendance.db'

print(f"Connecting to database at: {DB_PATH}")

# Mapping of updates by user ID
# Fields: department, position, phone, cnic, salary, join_date, notes
USER_UPDATES = {
    # 1. Leadership / Key Staff explicitly requested
    38: {
        "department": "AI & Data Science",
        "position": "AI Engineer & Team Lead",
        "phone": "0300-4567890",
        "cnic": "35202-1234567-1",
        "salary": 250000.0,
        "join_date": "2024-01-15",
        "notes": "Team Lead - AI Vision & Deep Learning Pipeline"
    },
    41: {
        "department": "Executive Management",
        "position": "Competency Head",
        "phone": "0300-8451234",
        "cnic": "35201-9876543-1",
        "salary": 350000.0,
        "join_date": "2023-08-01",
        "notes": "Executive Competency Head & Technical Advisor"
    },
    49: {
        "department": "Sales & Marketing",
        "position": "Sales Head",
        "phone": "0321-4561234",
        "cnic": "35202-5432167-3",
        "salary": 300000.0,
        "join_date": "2023-11-01",
        "notes": "Head of Enterprise & Regional Sales"
    },
    94: {
        "department": "Operations & Management",
        "position": "General Supervisor",
        "phone": "0301-7896541",
        "cnic": "35202-6789123-5",
        "salary": 220000.0,
        "join_date": "2024-02-10",
        "notes": "General Supervisor & Academic Coordinator"
    },

    # 2. Software Developers & Engineers
    46: {
        "department": "Software Development",
        "position": "Senior Full Stack Developer",
        "phone": "0312-3456789",
        "cnic": "35202-2345678-3",
        "salary": 175000.0,
        "join_date": "2024-03-01",
        "notes": "Full Stack Web & API Specialist"
    },
    48: {
        "department": "Software Development",
        "position": "Backend Python Developer",
        "phone": "0333-8765432",
        "cnic": "35202-3456789-5",
        "salary": 140000.0,
        "join_date": "2024-04-15",
        "notes": "Flask & Microservices Engineer"
    },
    51: {
        "department": "Software Development",
        "position": "Senior Frontend Developer",
        "phone": "0302-6549871",
        "cnic": "35202-4567890-7",
        "salary": 160000.0,
        "join_date": "2024-02-01",
        "notes": "UI/UX & Interactive Dashboard Specialist"
    },
    53: {
        "department": "Software Development",
        "position": "Mobile App Developer",
        "phone": "0345-1237894",
        "cnic": "35202-5678901-9",
        "salary": 135000.0,
        "join_date": "2024-05-10",
        "notes": "Cross-Platform Flutter & iOS Engineer"
    },
    54: {
        "department": "Software Development",
        "position": "DevOps & Cloud Engineer",
        "phone": "0322-9874561",
        "cnic": "35202-6789012-1",
        "salary": 155000.0,
        "join_date": "2024-03-20",
        "notes": "Docker, Kubernetes & Infrastructure Lead"
    },
    56: {
        "department": "Software Development",
        "position": "Frontend React Developer",
        "phone": "0305-4561237",
        "cnic": "35202-7890123-3",
        "salary": 125000.0,
        "join_date": "2024-06-01",
        "notes": "Frontend & Real-time WebSockets"
    },
    57: {
        "department": "Software Development",
        "position": "QA & Automation Engineer",
        "phone": "0313-7894561",
        "cnic": "35202-8901234-5",
        "salary": 110000.0,
        "join_date": "2024-06-15",
        "notes": "Automated Quality Assurance"
    },
    78: {
        "department": "Software Development",
        "position": "System Integration QA",
        "phone": "0300-0000078",
        "cnic": "35202-0000078-1",
        "salary": 80000.0,
        "join_date": "2024-09-12",
        "notes": "Test & Validation Profile"
    },
    79: {
        "department": "Software Development",
        "position": "Biometric Verification QA",
        "phone": "0300-0000079",
        "cnic": "35202-0000079-1",
        "salary": 85000.0,
        "join_date": "2024-09-12",
        "notes": "Facial Recognition Model Verification"
    },

    # 3. Sales & Marketing Team
    58: {
        "department": "Sales & Marketing",
        "position": "Senior Sales Executive",
        "phone": "0307-1234568",
        "cnic": "35202-9012345-7",
        "salary": 95000.0,
        "join_date": "2024-04-01",
        "notes": "Corporate Client Acquisition"
    },
    61: {
        "department": "Sales & Marketing",
        "position": "Business Development Manager",
        "phone": "0324-4567891",
        "cnic": "35202-0123456-9",
        "salary": 130000.0,
        "join_date": "2024-03-15",
        "notes": "Enterprise Strategic Partnerships"
    },
    93: {
        "department": "Sales & Marketing",
        "position": "Digital Marketing Specialist",
        "phone": "0334-6549872",
        "cnic": "35202-1357924-1",
        "salary": 85000.0,
        "join_date": "2024-07-01",
        "notes": "Online Campaigns & SEO"
    },

    # 4. Academic & Training (Students / Trainees)
    72: {
        "department": "Academic & Training",
        "position": "Research Intern (AI/ML)",
        "phone": "0308-7654321",
        "cnic": "35202-2468135-3",
        "salary": 45000.0,
        "join_date": "2024-09-01",
        "notes": "Computer Vision Research Intern"
    },
    73: {
        "department": "Academic & Training",
        "position": "Student Trainee",
        "phone": "0315-9876542",
        "cnic": "35202-3579246-5",
        "salary": 35000.0,
        "join_date": "2024-09-01",
        "notes": "Junior Developer Trainee"
    },
    76: {
        "department": "Academic & Training",
        "position": "Student Trainee",
        "phone": "0323-4561239",
        "cnic": "35202-4681357-7",
        "salary": 35000.0,
        "join_date": "2024-09-01",
        "notes": "Python Trainee"
    },
    77: {
        "department": "Academic & Training",
        "position": "Student Trainee",
        "phone": "0346-7894562",
        "cnic": "35202-5792468-9",
        "salary": 35000.0,
        "join_date": "2024-09-01",
        "notes": "AI Bootcamp Fellow"
    },
    80: {
        "department": "Academic & Training",
        "position": "School Apprentice",
        "phone": "0309-1234560",
        "cnic": "35202-6813579-1",
        "salary": 30000.0,
        "join_date": "2024-09-10",
        "notes": "Technical Program Scholar"
    },
    81: {
        "department": "Academic & Training",
        "position": "School Apprentice",
        "phone": "0316-2345671",
        "cnic": "35202-7924681-3",
        "salary": 30000.0,
        "join_date": "2024-09-10",
        "notes": "Scholarship Fellow"
    },
    82: {
        "department": "Academic & Training",
        "position": "School Apprentice",
        "phone": "0325-3456782",
        "cnic": "35202-8135792-5",
        "salary": 30000.0,
        "join_date": "2024-09-10",
        "notes": "Apprenticeship Program"
    },
    83: {
        "department": "Academic & Training",
        "position": "School Apprentice",
        "phone": "0335-4567893",
        "cnic": "35202-9246813-7",
        "salary": 30000.0,
        "join_date": "2024-09-10",
        "notes": "Apprenticeship Program"
    },
    84: {
        "department": "Academic & Training",
        "position": "School Apprentice",
        "phone": "0347-5678904",
        "cnic": "35202-0357924-9",
        "salary": 30000.0,
        "join_date": "2024-09-15",
        "notes": "Apprenticeship Program"
    },
    85: {
        "department": "Academic & Training",
        "position": "School Apprentice",
        "phone": "0304-6789015",
        "cnic": "35202-1468135-1",
        "salary": 30000.0,
        "join_date": "2024-09-15",
        "notes": "Apprenticeship Program"
    },
    86: {
        "department": "Academic & Training",
        "position": "School Apprentice",
        "phone": "0317-7890126",
        "cnic": "35202-2579246-3",
        "salary": 30000.0,
        "join_date": "2024-09-15",
        "notes": "Apprenticeship Program"
    },
    87: {
        "department": "Academic & Training",
        "position": "School Apprentice",
        "phone": "0326-8901237",
        "cnic": "35202-3681357-5",
        "salary": 30000.0,
        "join_date": "2024-09-15",
        "notes": "Apprenticeship Program"
    },
    89: {
        "department": "Academic & Training",
        "position": "School Apprentice",
        "phone": "0336-9012348",
        "cnic": "35202-4792468-7",
        "salary": 30000.0,
        "join_date": "2024-09-15",
        "notes": "Apprenticeship Program"
    },
    90: {
        "department": "Academic & Training",
        "position": "School Apprentice",
        "phone": "0348-0123459",
        "cnic": "35202-5813579-9",
        "salary": 30000.0,
        "join_date": "2024-09-15",
        "notes": "Apprenticeship Program"
    },
    91: {
        "department": "Academic & Training",
        "position": "School Apprentice",
        "phone": "0306-1234561",
        "cnic": "35202-6924681-1",
        "salary": 30000.0,
        "join_date": "2024-09-15",
        "notes": "Apprenticeship Program"
    },
    92: {
        "department": "Academic & Training",
        "position": "School Apprentice",
        "phone": "0318-2345672",
        "cnic": "35202-7135792-3",
        "salary": 30000.0,
        "join_date": "2024-09-15",
        "notes": "Apprenticeship Program"
    },

    # 5. FnK Operations Team
    95: {
        "department": "FnK Operations",
        "position": "Floor Supervisor",
        "phone": "0301-9595951",
        "cnic": "35202-9595951-1",
        "salary": 85000.0,
        "join_date": "2024-09-29",
        "notes": "Dining & Floor Management"
    },
    96: {
        "department": "FnK Operations",
        "position": "Assistant Chef",
        "phone": "0301-9696962",
        "cnic": "35202-9696962-2",
        "salary": 90000.0,
        "join_date": "2024-09-29",
        "notes": "Culinary & Kitchen Lead"
    },
    97: {
        "department": "FnK Operations",
        "position": "Kitchen Specialist",
        "phone": "0301-9797973",
        "cnic": "35202-9797973-3",
        "salary": 65000.0,
        "join_date": "2024-09-29",
        "notes": "Culinary Prep Staff"
    },
    98: {
        "department": "FnK Operations",
        "position": "Inventory Controller",
        "phone": "0301-9898984",
        "cnic": "35202-9898984-4",
        "salary": 70000.0,
        "join_date": "2024-09-29",
        "notes": "Supply Chain & Storage"
    },
    99: {
        "department": "FnK Operations",
        "position": "Procurement Officer",
        "phone": "0301-9999995",
        "cnic": "35202-9999995-5",
        "salary": 75000.0,
        "join_date": "2024-09-29",
        "notes": "Vendor Management & Purchasing"
    }
}

with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    updated_count = 0
    for uid, data in USER_UPDATES.items():
        cursor.execute("""
            UPDATE users 
            SET department = ?,
                position = ?,
                phone = COALESCE(phone, ?),
                cnic = ?,
                salary = ?,
                join_date = ?,
                notes = ?
            WHERE id = ?
        """, (
            data["department"],
            data["position"],
            data["phone"],
            data["cnic"],
            data["salary"],
            data["join_date"],
            data["notes"],
            uid
        ))
        if cursor.rowcount > 0:
            updated_count += 1
            print(f"[OK] Updated user ID {uid}: {data['position']} ({data['department']})")

    # If phone was empty/null or "None", fill it
    for uid, data in USER_UPDATES.items():
        cursor.execute("""
            UPDATE users 
            SET phone = ?
            WHERE id = ? AND (phone IS NULL OR phone = '' OR phone = 'None')
        """, (data["phone"], uid))

    # Also update any null emails with clean fallbacks
    cursor.execute("UPDATE users SET email = 'test.user@qintellect.ai' WHERE id = 78 AND (email IS NULL OR email = '' OR email = 'None')")
    cursor.execute("UPDATE users SET email = 'verification@qintellect.ai' WHERE id = 79 AND (email IS NULL OR email = '' OR email = 'None')")

    conn.commit()
    print(f"\nSuccessfully committed {updated_count} user updates to database.")
