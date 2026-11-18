import unittest
import tempfile
from pathlib import Path
from economia_ontology import initialize_database, validate_database
from economia_reference_suite import run_reference_suite

class TestOntology(unittest.TestCase):
    def test_schema_initializes_and_validates(self):
        with tempfile.TemporaryDirectory() as d:
            conn=initialize_database(Path(d)/'ontology.sqlite')
            self.assertEqual(validate_database(conn), [])
            self.assertGreater(conn.execute('SELECT COUNT(*) FROM ontology_class').fetchone()[0], 5)
            self.assertGreater(conn.execute('SELECT COUNT(*) FROM relation_type').fetchone()[0], 5)
            conn.close()

    def test_foreign_keys_reject_unknown_class(self):
        with tempfile.TemporaryDirectory() as d:
            conn=initialize_database(Path(d)/'ontology.sqlite')
            with self.assertRaises(Exception):
                conn.execute("INSERT INTO economic_entity(entity_id,class_code,name) VALUES ('x','NO_CLASS','X')")
            conn.close()


    def test_mode_separation_and_relation_types(self):
        with tempfile.TemporaryDirectory() as d:
            conn=initialize_database(Path(d)/'ontology.sqlite')
            conn.execute("INSERT INTO project VALUES ('p-real','Real','real','2026-01-01')")
            conn.execute("INSERT INTO project VALUES ('p-sim','Simulation','simulation','2026-01-01')")
            conn.execute("INSERT INTO geography(geography_id,name,geography_type) VALUES ('DE','Germany','country')")
            conn.execute("INSERT INTO economic_entity(entity_id,class_code,name) VALUES ('factory','ECO-ENT','Factory')")
            conn.execute("INSERT INTO economic_entity(entity_id,class_code,name) VALUES ('steel','ECO-GOOD','Steel')")
            conn.execute("INSERT INTO economic_relation(subject_id,relation_code,object_id) VALUES ('factory','PRODUCES','steel')")
            with self.assertRaises(Exception):
                conn.execute("INSERT INTO economic_relation(subject_id,relation_code,object_id) VALUES ('steel','PRODUCES','factory')")
            conn.commit()
            conn.close()


    def test_calculation_run_cannot_cross_project_modes(self):
        with tempfile.TemporaryDirectory() as d:
            conn=initialize_database(Path(d)/'ontology.sqlite')
            conn.execute("INSERT INTO project VALUES ('p-real','Real','real','2026-01-01')")
            conn.execute("INSERT INTO model_registry VALUES ('M01','1.0','Balance','accounting','tested','{}')")
            with self.assertRaises(Exception):
                conn.execute("""INSERT INTO calculation_run
                    (run_id,project_id,model_id,model_version,mode,parameters_json,software_version,validation_status,started_at)
                    VALUES ('r1','p-real','M01','1.0','simulation','{}','test','UNVERIFIED','2026-01-01')""")
            conn.close()

class TestReferenceSuite(unittest.TestCase):
    def test_all_reference_fixtures_pass(self):
        result=run_reference_suite()
        self.assertEqual(result['count'],14)
        self.assertEqual(result['passed'],14)
        self.assertTrue(result['all_passed'])

if __name__=='__main__': unittest.main(verbosity=2)
