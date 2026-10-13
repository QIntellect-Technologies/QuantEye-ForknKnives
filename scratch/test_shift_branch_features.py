import unittest
import json
import sys
sys.path.insert(0, '.')
from app import app
import database as db

class ShiftBranchFeatureTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_get_shifts(self):
        res = self.client.get('/api/shifts')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['shifts']), 0)

    def test_individual_shift_assignment(self):
        users = db.get_all_users()
        if users:
            uid = users[0]['id']
            res = self.client.post(f'/api/users/{uid}/assign-shift', json={'shift_id': 1})
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data)
            self.assertTrue(data['success'])

    def test_bulk_shift_assignment(self):
        users = db.get_all_users()
        if users:
            uids = [users[0]['id']]
            res = self.client.post('/api/users/bulk-assign-shifts', json={'user_ids': uids, 'shift_id': 1})
            self.assertEqual(res.status_code, 200)
            data = json.loads(res.data)
            self.assertTrue(data['success'])

    def test_branch_settings(self):
        res = self.client.get('/api/settings/branch')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn('branch_name', data)

if __name__ == '__main__':
    unittest.main()
