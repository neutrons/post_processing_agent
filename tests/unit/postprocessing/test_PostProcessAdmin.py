from postprocessing.PostProcessAdmin import PostProcessAdmin

# third-party imports
import pytest


def createEmptyFile(filename):
    with open(filename, "w"):
        pass


def test_bad_constructor():
    # require that it fails if nothing is provided
    with pytest.raises(TypeError):
        _ = PostProcessAdmin()


if __name__ == "__main__":
    pytest.main([__file__])
