import unittest
from audit_core import audit_event_hash, verify_audit_rows


class AuditChainTests(unittest.TestCase):
    def _rows(self):
        rows=[];prev=''
        for i in range(3):
            row={'prev_hash':prev,'actor':'admin:root','action':f'action_{i}','entity_type':'exam','entity_id':str(i),'details':'ok','created_at':f'2026-08-15T00:0{i}:00+00:00'}
            row['event_hash']=audit_event_hash(**row)
            rows.append(row);prev=row['event_hash']
        return rows

    def test_chain_verifies(self):
        result=verify_audit_rows(self._rows())
        self.assertTrue(result['valid'])
        self.assertEqual(result['checked'],3)

    def test_content_tampering_is_detected(self):
        rows=self._rows();rows[1]['details']='altered'
        self.assertFalse(verify_audit_rows(rows)['valid'])

    def test_hash_link_tampering_is_detected(self):
        rows=self._rows();rows[2]['prev_hash']='0'*64
        self.assertFalse(verify_audit_rows(rows)['valid'])

    def test_hash_is_deterministic(self):
        args=dict(prev_hash='',actor='a',action='b',entity_type='c',entity_id='d',details='e',created_at='f')
        self.assertEqual(audit_event_hash(**args),audit_event_hash(**args))


if __name__=='__main__':unittest.main()
