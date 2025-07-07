"""
Integration tests for plot_publisher with dynamic plotly version injection.
This demonstrates the end-to-end functionality as requested in the user story.
"""
import pytest
from unittest.mock import patch, MagicMock
from plot_publisher import plot1d, plot_heatmap, publish_plot


@pytest.fixture
def mock_config():
    """Fixture to mock the configuration."""
    with patch("plot_publisher._plot_publisher.read_configuration") as mock_read_config:
        mock_config_obj = MagicMock()
        mock_config_obj.publish_url_template = (
            "http://test-server.com/publish/${instrument}/${run_number}"
        )
        mock_config_obj.publisher_username = "testuser"
        mock_config_obj.publisher_password = "testpass"
        mock_config_obj.publisher_certificate = ""
        mock_read_config.return_value = mock_config_obj
        yield mock_read_config


class TestPlotPublisherIntegration:
    """Integration tests demonstrating dynamic plotly version functionality."""

    def test_plot1d_with_different_plotly_versions(self, mock_config):
        """Test that plot1d works with different plotly versions and injects version correctly."""
        x = [1, 2, 3, 4, 5]
        y = [2, 4, 6, 8, 10]

        # Test with plotly version 5.15.0
        with patch("requests.post") as mock_post, patch("plotly.__version__", "5.15.0"):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            response = plot1d(
                run_number=12345,
                data_list=[[x, y]],
                instrument="TEST",
                title="Integration Test Plot",
                x_title="X Values",
                y_title="Y Values",
                publish=True,
            )

            # Verify the response and call were made
            assert response.status_code == 200
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            posted_files = call_args.kwargs["files"]

            # Verify that the plotlyjs-version was injected
            plot_content = posted_files["file"]
            assert 'plotlyjs-version="5.15.0"' in plot_content
            assert "id=" in plot_content  # Should have a plotly div ID

        # Test with a different plotly version
        with patch("requests.post") as mock_post2, patch(
            "plotly.__version__", "5.17.2"
        ):
            mock_response2 = MagicMock()
            mock_response2.status_code = 200
            mock_post2.return_value = mock_response2

            response2 = plot1d(
                run_number=12346,
                data_list=[[x, y]],
                instrument="TEST",
                title="Integration Test Plot 2",
                publish=True,
            )

            # Verify the response and new version was injected
            assert response2.status_code == 200
            call_args2 = mock_post2.call_args
            posted_files2 = call_args2.kwargs["files"]
            plot_content2 = posted_files2["file"]
            assert 'plotlyjs-version="5.17.2"' in plot_content2

    def test_plot_heatmap_with_version_injection(self, mock_config):
        """Test that plot_heatmap also gets version injection."""
        x = [1, 2, 3]
        y = [1, 2, 3]
        z = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

        with patch("requests.post") as mock_post, patch("plotly.__version__", "5.16.1"):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            response = plot_heatmap(
                run_number=54321,
                x=x,
                y=y,
                z=z,
                instrument="HEATMAP_TEST",
                title="Integration Heatmap Test",
                publish=True,
            )

            # Verify the response and version was injected into heatmap
            assert response.status_code == 200
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            posted_files = call_args.kwargs["files"]
            plot_content = posted_files["file"]
            assert 'plotlyjs-version="5.16.1"' in plot_content

    def test_publish_plot_custom_div_with_version_injection(self, mock_config):
        """Test publish_plot with a custom div (like MrRed would use)."""
        # This simulates the MrRed use case where they construct their own plot div
        custom_plot_div = """
        <div id="custom-plot-12345" class="plotly-graph-div" style="height:600px; width:100%;">
            <script type="text/javascript">
                // Custom plotly code here
                Plotly.newPlot('custom-plot-12345', data, layout);
            </script>
        </div>
        """

        with patch("requests.post") as mock_post, patch("plotly.__version__", "5.18.0"):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            response = publish_plot(
                instrument="CUSTOM", run_number=99999, files={"file": custom_plot_div}
            )

            # Verify the response and version was injected into the custom div
            assert response.status_code == 200
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            posted_files = call_args.kwargs["files"]
            plot_content = posted_files["file"]

            assert 'plotlyjs-version="5.18.0"' in plot_content
            assert 'id="custom-plot-12345"' in plot_content
            assert "Plotly.newPlot" in plot_content  # Original content preserved

    def test_publish_plot_multiple_files_mixed_content(self, mock_config):
        """Test publish_plot with multiple files of different types."""
        files = {
            "main_plot": '<div id="main-plot" class="plotly-graph-div">Main plot</div>',
            "secondary_plot": '<div id="secondary-plot" class="plotly-graph-div">Secondary</div>',
            "data_file": "run_number,counts\n12345,1000\n12346,1200",
            "metadata": '{"instrument": "TEST", "timestamp": "2024-01-01"}',
            "readme": "This experiment measured neutron scattering...",
        }

        with patch("requests.post") as mock_post, patch("plotly.__version__", "5.19.0"):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            response = publish_plot(
                instrument="MULTI_FILE", run_number=77777, files=files
            )

            # Verify the response and version injection behavior
            assert response.status_code == 200
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            posted_files = call_args.kwargs["files"]

            # Plot divs should have version injected
            assert 'plotlyjs-version="5.19.0"' in posted_files["main_plot"]
            assert 'plotlyjs-version="5.19.0"' in posted_files["secondary_plot"]

            # Non-HTML files should be unchanged
            assert posted_files["data_file"] == files["data_file"]
            assert posted_files["metadata"] == files["metadata"]
            assert posted_files["readme"] == files["readme"]

    def test_backwards_compatibility(self, mock_config):
        """Test that the changes maintain backwards compatibility."""
        # This test ensures that existing autoreduction scripts will continue to work
        x = [0, 1, 2, 3, 4]
        y = [0, 1, 4, 9, 16]  # y = x^2

        with patch("requests.post") as mock_post, patch("plotly.__version__", "5.15.0"):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            # Test the single dataset format (list of [x, y] pairs)
            response = plot1d(
                run_number=11111,
                data_list=[[x, y]],  # Single dataset wrapped in list
                instrument="BACKWARDS_COMPAT",
                publish=True,
            )

            assert response.status_code == 200

            # Verify version was still injected
            call_args = mock_post.call_args
            posted_files = call_args.kwargs["files"]
            assert 'plotlyjs-version="5.15.0"' in posted_files["file"]


if __name__ == "__main__":
    pytest.main([__file__])
