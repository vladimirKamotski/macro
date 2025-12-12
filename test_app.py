
import unittest
import json
from app import app
from pricing import VanillaFxOptionPricer, VolatilitySurface

class TestApp(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_risk_reversal_vol(self):
        # Test 25 Delta RR
        # Surface: ATM=0.10, RR25=0.02, ST25=0.0
        # RR25 = Vol(25C) - Vol(25P) = 0.02
        # ST25 = 0.5*(Vol(25C)+Vol(25P)) - ATM = 0 -> Avg(25C, 25P) = ATM = 0.10
        # So we expect Vol(25C) = 0.11, Vol(25P) = 0.09
        # The returned 'vol' for RR should be (0.11 + 0.09)/2 = 0.10
        
        payload = {
            'spot_ref': 100.0,
            'rd': 0.0,
            'forward': 100.0,
            'T': 1.0,
            'atm': 0.10,
            'rr25': 0.02,
            'st25': 0.00,
            'rr10': 0.00,
            'st10': 0.00,
            'type': 'risk_reversal',
            'strike_type': 'delta',
            'strike': 0.25
        }
        
        response = self.app.post('/calculate', 
                                 data=json.dumps(payload),
                                 content_type='application/json')
        
        data = json.loads(response.data)
        
        self.assertTrue(data['success'], msg=f"Request failed: {data.get('message')}")
        
        # Verify returned vol
        returned_vol = data['vol']
        expected_vol = 0.10
        
        print(f"Returned Vol: {returned_vol}, Expected: {expected_vol}")
        
        self.assertAlmostEqual(returned_vol, expected_vol, places=4)
        
        # Also check price roughly
        # Price = Call(0.11) - Put(0.09)
        # 25 Delta Call/Put means rough strikes.
        # This is more about checking that the app logic averages them correctly.

if __name__ == '__main__':
    unittest.main()
