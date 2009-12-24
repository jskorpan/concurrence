build:
	$(PYTHON) setup.py build

ext:
	$(PYTHON) setup.py build_ext --inplace
	
egg:
	$(PYTHON) setup.py bdist_egg
				
install:
	$(PYTHON) setup.py install

sdist:
	$(PYTHON) setup.py sdist

_doc:
	cd doc/src; make html
 
doc: _doc

clean:
	-find . -name *.pyc -exec rm -rf {} \;
	-find . -name *.so -exec rm -rf {} \;
	-find . -name *.dep -exec rm -rf {} \;
	-find . -name *~ -exec rm -rf {} \;
	-find . -name *.egg-info -exec rm -rf {} \;
	rm -rf setuptools*.egg
	rm -rf doc/src/_build
	rm -rf build dist
	rm -rf lib/concurrence/database/mysql/concurrence.database.mysql._mysql.c
	rm -rf lib/concurrence/concurrence._event.c
	rm -rf lib/concurrence/io/concurrence.io._io.c
	rm -rf test/htmlcov

dist_clean: clean
	find . -name .svn -exec rm -rf {} \;

_test: 
	cd test; make test

test: _test 

coverage:
	cd test; coverage erase
	cd test; PYTHON="coverage run -a " make test
	cd test; rm -rf htmlcov
	cd test; coverage html -d htmlcov
	firefox test/htmlcov/index.html& 
