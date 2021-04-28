-----------------
Running the tests
-----------------
.. _running_tests:

The tests for this project are all written using `pytest <https://docs.pytest.org/en/latest>`_.

.. code-block:: shell

   $ python -m pytest tests/

This is one of the ways `pytest allows for selecting tests <https://docs.pytest.org/en/latest/usage.html#specifying-tests-selecting-tests>`_.
Specifying a directory or file will run all tests within that directory (recursively) or file.
Specifying a regular expression using ``-k`` will select all tests that match the regular expression independent of where they are defined



----------------------------------------
Running manual tests for mantidpython.py
----------------------------------------

.. _running_manual_tests:

Manual tests can be executed as

.. code-blocks:: shell

   $ python2 scripts/mantidpython.py /SNS/HYP/shared/auto_reduction/reduce_HYS.py [HYS nexus file] [Output Dir]

or

.. code-blocks:: shell

   $ python scripts/mantidpython.py tests/reduce_CONDA.py [Data file]  [Output dir]

as an example for how to activating a specific conda environment for reduction.