import os
import server
import unittest
import tempfile

class PRTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, server.app.config['DATABASE'] = tempfile.mkstemp()
        server.app.config['TESTING'] = True
        self.app = server.app.test_client()
        server.initdb()
    
    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(server.app.config['DATABASE'])
    
    def test_empty_db(self):
        rv = self.app.get('/items')
        assert 'no items' in rv.data
    
    def test_categories(self):
        rv = self.app.get('/categories')
        for a in ['Camera', 'Projector', 'Modem', 'Printer']:
            print "Testing that %s is in database." % a
            assert a in rv.data
    
    def llogin(self, username, password):
        print "Testing %s:%s" % (username, password)
        rv = self.app.post('/login', data=dict(username='admin', password='admin'), follow_redirects=True)
        assert "Logged in success" in rv.data

    def test_login(self):
        self.llogin('admin', 'admin')
        self.llogin('jnhdny', 's7eel')

if __name__ == '__main__':
    unittest.main()