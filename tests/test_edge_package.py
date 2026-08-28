import copy
import unittest

from edge_package import make_envelope, verify_envelope, seal_envelope, open_sealed_envelope


class EdgePackageTests(unittest.TestCase):
    KEY='test-edge-signing-key-0123456789-abcdefghijklmnopqrstuvwxyz'
    PAYLOAD={'kind':'exam','exam':{'title':'Pilot','duration_minutes':30},'questions':[{'question':'2+2?','answer_key':'B'}]}

    def test_round_trip(self):
        env=make_envelope(self.PAYLOAD,self.KEY)
        self.assertEqual(verify_envelope(env,self.KEY),self.PAYLOAD)

    def test_payload_tampering_is_detected(self):
        env=make_envelope(self.PAYLOAD,self.KEY);tampered=copy.deepcopy(env);tampered['payload']['exam']['duration_minutes']=60
        with self.assertRaises(ValueError):verify_envelope(tampered,self.KEY)

    def test_signature_tampering_is_detected(self):
        env=make_envelope(self.PAYLOAD,self.KEY);env['signature']='0'*64
        with self.assertRaises(ValueError):verify_envelope(env,self.KEY)

    def test_short_key_rejected(self):
        with self.assertRaises(ValueError):make_envelope(self.PAYLOAD,'short')

    def test_sealed_round_trip_hides_plaintext(self):
        env=seal_envelope(self.PAYLOAD,self.KEY)
        self.assertNotIn('Pilot',str(env))
        self.assertEqual(open_sealed_envelope(env,self.KEY),self.PAYLOAD)

    def test_sealed_ciphertext_tampering_is_detected(self):
        env=seal_envelope(self.PAYLOAD,self.KEY);env['ciphertext']=env['ciphertext'][:-2]+'AA'
        with self.assertRaises(ValueError):open_sealed_envelope(env,self.KEY)



if __name__=='__main__':unittest.main()
