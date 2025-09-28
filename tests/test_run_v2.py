"""
Tests for bot/run_v2.py
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from bot.run_v2 import (
    run_daily_digest,
    run_mini_digest,
    run_test_scenarios,
    run_quarterly_lda_ingest,
    run_web_server,
    main,
)


class TestRunV2:
    """Test run_v2 module functions"""

    @patch("bot.run_v2.DailySignalsCollectorV2")
    @patch("bot.run_v2.DigestV2Formatter")
    @patch("bot.run_v2.SignalsDatabaseV2")
    def test_run_daily_digest_success(
        self, mock_database_class, mock_formatter_class, mock_collector_class
    ):
        """Test successful daily digest run"""
        # Mock components
        mock_collector = Mock()
        mock_formatter = Mock()
        mock_database = Mock()
        
        mock_collector_class.return_value = mock_collector
        mock_formatter_class.return_value = mock_formatter
        mock_database_class.return_value = mock_database
        
        # Mock data
        mock_signals = [Mock()]
        mock_digest = "Test Daily Digest"
        mock_watchlist = [{"name": "Google"}, {"name": "privacy"}]
        
        mock_collector.collect_all_signals.return_value = mock_signals
        mock_database.get_watchlist.return_value = mock_watchlist
        mock_formatter.format_daily_digest.return_value = mock_digest
        
        # Test
        result = run_daily_digest(hours_back=24, channel_id="test_channel")
        
        # Verify
        mock_collector_class.assert_called_once()
        mock_formatter_class.assert_called_once()
        mock_database_class.assert_called_once()
        mock_collector.collect_all_signals.assert_called_once_with(24)
        mock_database.get_watchlist.assert_called_once_with("test_channel")
        mock_formatter.format_daily_digest.assert_called_once_with(mock_signals, 24)
        assert result == mock_digest

    @patch("bot.run_v2.DailySignalsCollectorV2")
    @patch("bot.run_v2.DigestV2Formatter")
    @patch("bot.run_v2.SignalsDatabaseV2")
    def test_run_daily_digest_with_custom_params(
        self, mock_database_class, mock_formatter_class, mock_collector_class
    ):
        """Test daily digest with custom parameters"""
        # Mock components
        mock_collector = Mock()
        mock_formatter = Mock()
        mock_database = Mock()
        
        mock_collector_class.return_value = mock_collector
        mock_formatter_class.return_value = mock_formatter
        mock_database_class.return_value = mock_database
        
        # Mock data
        mock_signals = [Mock()]
        mock_digest = "Test Daily Digest"
        mock_watchlist = []
        
        mock_collector.collect_all_signals.return_value = mock_signals
        mock_database.get_watchlist.return_value = mock_watchlist
        mock_formatter.format_daily_digest.return_value = mock_digest
        
        # Test with custom parameters
        result = run_daily_digest(hours_back=12, channel_id="custom_channel")
        
        # Verify
        mock_collector.collect_all_signals.assert_called_once_with(12)
        mock_database.get_watchlist.assert_called_once_with("custom_channel")
        assert result == mock_digest

    @patch("bot.run_v2.DailySignalsCollectorV2")
    @patch("bot.run_v2.DigestV2Formatter")
    @patch("bot.run_v2.SignalsDatabaseV2")
    def test_run_mini_digest_success(
        self, mock_database_class, mock_formatter_class, mock_collector_class
    ):
        """Test successful mini digest run"""
        # Mock components
        mock_collector = Mock()
        mock_formatter = Mock()
        mock_database = Mock()
        
        mock_collector_class.return_value = mock_collector
        mock_formatter_class.return_value = mock_formatter
        mock_database_class.return_value = mock_database
        
        # Mock data
        mock_signals = [Mock()]
        mock_mini_digest = "Test Mini Digest"
        mock_watchlist = [{"name": "Microsoft"}]
        
        mock_collector.collect_all_signals.return_value = mock_signals
        mock_database.get_watchlist.return_value = mock_watchlist
        mock_formatter.format_mini_digest.return_value = mock_mini_digest
        
        # Test
        result = run_mini_digest(hours_back=4, channel_id="test_channel")
        
        # Verify
        mock_collector.collect_all_signals.assert_called_once_with(4)
        mock_database.get_watchlist.assert_called_once_with("test_channel")
        mock_formatter.format_mini_digest.assert_called_once_with(mock_signals)
        assert result == mock_mini_digest

    @patch("bot.run_v2.DailySignalsCollectorV2")
    @patch("bot.run_v2.DigestV2Formatter")
    @patch("bot.run_v2.SignalsDatabaseV2")
    def test_run_mini_digest_no_digest(
        self, mock_database_class, mock_formatter_class, mock_collector_class
    ):
        """Test mini digest when no digest is generated"""
        # Mock components
        mock_collector = Mock()
        mock_formatter = Mock()
        mock_database = Mock()
        
        mock_collector_class.return_value = mock_collector
        mock_formatter_class.return_value = mock_formatter
        mock_database_class.return_value = mock_database
        
        # Mock data - no signals
        mock_signals = []
        mock_watchlist = []
        
        mock_collector.collect_all_signals.return_value = mock_signals
        mock_database.get_watchlist.return_value = mock_watchlist
        mock_formatter.format_mini_digest.return_value = None  # No digest generated
        
        # Test
        result = run_mini_digest(hours_back=4, channel_id="test_channel")
        
        # Verify
        assert result is None

    @patch("bot.run_v2.TestFixturesV2")
    @patch("bot.run_v2.TestValidator")
    @patch("bot.signals_v2.SignalsRulesEngine")
    @patch("bot.run_v2.DigestV2Formatter")
    def test_run_test_scenarios(
        self, mock_formatter_class, mock_rules_engine_class, mock_validator_class, mock_fixtures_class
    ):
        """Test running test scenarios"""
        # Mock components
        mock_fixtures = Mock()
        mock_validator = Mock()
        mock_rules_engine = Mock()
        mock_formatter = Mock()
        
        mock_fixtures_class.return_value = mock_fixtures
        mock_validator_class.return_value = mock_validator
        mock_rules_engine_class.return_value = mock_rules_engine
        mock_formatter_class.return_value = mock_formatter
        
        # Mock test data
        mock_signals = [Mock()]
        mock_digest = "Test Digest"
        mock_validation_report = "Validation Report"
        
        mock_fixtures.get_fixture_a_mixed_day.return_value = mock_signals
        mock_fixtures.get_fixture_b_watchlist_hit.return_value = mock_signals
        mock_fixtures.get_fixture_c_mini_digest_threshold.return_value = mock_signals
        mock_fixtures.get_fixture_d_character_budget_stress.return_value = mock_signals
        mock_fixtures.get_fixture_e_timezone_test.return_value = mock_signals
        
        mock_rules_engine.process_signal.return_value = Mock()
        mock_formatter.format_daily_digest.return_value = mock_digest
        mock_validator.get_validation_report.return_value = mock_validation_report
        
        # Test
        run_test_scenarios()
        
        # Verify all fixtures were called
        assert mock_fixtures.get_fixture_a_mixed_day.call_count == 1
        assert mock_fixtures.get_fixture_b_watchlist_hit.call_count == 1
        assert mock_fixtures.get_fixture_c_mini_digest_threshold.call_count == 1
        assert mock_fixtures.get_fixture_d_character_budget_stress.call_count == 1
        assert mock_fixtures.get_fixture_e_timezone_test.call_count == 1
        
        # Verify validation was called for each scenario
        assert mock_validator.validate_digest_format.call_count == 5
        assert mock_validator.validate_section_limits.call_count == 5
        assert mock_validator.validate_mobile_formatting.call_count == 5
        assert mock_validator.validate_timezone_handling.call_count == 5

    def test_run_quarterly_lda_ingest(self):
        """Test quarterly LDA ingest (placeholder)"""
        # This is a placeholder function, so we just test it doesn't raise
        run_quarterly_lda_ingest()

    @patch("bot.web_server_v2.create_web_server_v2")
    @patch("bot.run_v2.os.environ.get")
    def test_run_web_server_default_port(self, mock_env_get, mock_create_server):
        """Test web server with default port"""
        # Mock environment
        mock_env_get.return_value = "8080"
        
        # Mock web server
        mock_app = Mock()
        mock_create_server.return_value = mock_app
        
        # Test
        run_web_server()
        
        # Verify
        mock_env_get.assert_any_call("PORT", 8000)
        mock_create_server.assert_called_once()
        mock_app.run.assert_called_once_with(host="0.0.0.0", port=8080, debug=False)

    @patch("bot.web_server_v2.create_web_server_v2")
    def test_run_web_server_custom_port(self, mock_create_server):
        """Test web server with custom port"""
        # Mock web server
        mock_app = Mock()
        mock_create_server.return_value = mock_app
        
        # Test
        run_web_server(port=9000)
        
        # Verify
        mock_create_server.assert_called_once()
        mock_app.run.assert_called_once_with(host="0.0.0.0", port=9000, debug=False)

    @patch("bot.run_v2.run_daily_digest")
    @patch("bot.run_v2.argparse.ArgumentParser")
    def test_main_daily_mode(self, mock_parser_class, mock_run_daily):
        """Test main function in daily mode"""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.mode = "daily"
        mock_args.hours = 24
        mock_args.channel = "test_channel"
        mock_args.dry_run = False
        mock_args.port = 8000
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        # Mock daily digest
        mock_run_daily.return_value = "Test Digest"
        
        # Test
        main()
        
        # Verify
        mock_run_daily.assert_called_once_with(24, "test_channel")

    @patch("bot.run_v2.run_mini_digest")
    @patch("bot.run_v2.argparse.ArgumentParser")
    def test_main_mini_mode(self, mock_parser_class, mock_run_mini):
        """Test main function in mini mode"""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.mode = "mini"
        mock_args.hours = 4
        mock_args.channel = "test_channel"
        mock_args.dry_run = False
        mock_args.port = 8000
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        # Mock mini digest
        mock_run_mini.return_value = "Test Mini Digest"
        
        # Test
        main()
        
        # Verify
        mock_run_mini.assert_called_once_with(4, "test_channel")

    @patch("bot.run_v2.run_mini_digest")
    @patch("bot.run_v2.argparse.ArgumentParser")
    def test_main_mini_mode_no_digest(self, mock_parser_class, mock_run_mini):
        """Test main function in mini mode when no digest is generated"""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.mode = "mini"
        mock_args.hours = 4
        mock_args.channel = "test_channel"
        mock_args.dry_run = False
        mock_args.port = 8000
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        # Mock mini digest - no digest generated
        mock_run_mini.return_value = None
        
        # Test
        main()
        
        # Verify
        mock_run_mini.assert_called_once_with(4, "test_channel")

    @patch("bot.run_v2.run_test_scenarios")
    @patch("bot.run_v2.argparse.ArgumentParser")
    def test_main_test_mode(self, mock_parser_class, mock_run_test):
        """Test main function in test mode"""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.mode = "test"
        mock_args.hours = 24
        mock_args.channel = "test_channel"
        mock_args.dry_run = False
        mock_args.port = 8000
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        # Test
        main()
        
        # Verify
        mock_run_test.assert_called_once()

    @patch("bot.run_v2.run_quarterly_lda_ingest")
    @patch("bot.run_v2.argparse.ArgumentParser")
    def test_main_quarterly_mode(self, mock_parser_class, mock_run_quarterly):
        """Test main function in quarterly mode"""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.mode = "quarterly"
        mock_args.hours = 24
        mock_args.channel = "test_channel"
        mock_args.dry_run = False
        mock_args.port = 8000
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        # Test
        main()
        
        # Verify
        mock_run_quarterly.assert_called_once()

    @patch("bot.run_v2.run_web_server")
    @patch("bot.run_v2.argparse.ArgumentParser")
    def test_main_server_mode(self, mock_parser_class, mock_run_server):
        """Test main function in server mode"""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.mode = "server"
        mock_args.hours = 24
        mock_args.channel = "test_channel"
        mock_args.dry_run = False
        mock_args.port = 9000
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        # Test
        main()
        
        # Verify
        mock_run_server.assert_called_once_with(9000)

    @patch("bot.run_v2.run_daily_digest")
    @patch("bot.run_v2.argparse.ArgumentParser")
    def test_main_dry_run(self, mock_parser_class, mock_run_daily):
        """Test main function with dry run flag"""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.mode = "daily"
        mock_args.hours = 24
        mock_args.channel = "test_channel"
        mock_args.dry_run = True
        mock_args.port = 8000
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        # Mock daily digest
        mock_run_daily.return_value = "Test Digest"
        
        # Test
        main()
        
        # Verify
        mock_run_daily.assert_called_once_with(24, "test_channel")

    @patch("bot.run_v2.run_daily_digest")
    @patch("bot.run_v2.argparse.ArgumentParser")
    def test_main_exception_handling(self, mock_parser_class, mock_run_daily):
        """Test main function exception handling"""
        # Mock parser
        mock_parser = Mock()
        mock_args = Mock()
        mock_args.mode = "daily"
        mock_args.hours = 24
        mock_args.channel = "test_channel"
        mock_args.dry_run = False
        mock_args.port = 8000
        mock_parser.parse_args.return_value = mock_args
        mock_parser_class.return_value = mock_parser
        
        # Mock exception
        mock_run_daily.side_effect = Exception("Test error")
        
        # Test - should raise the exception
        with pytest.raises(Exception, match="Test error"):
            main()

    def test_main_argument_parser_setup(self):
        """Test that argument parser is set up correctly"""
        from bot.run_v2 import main
        import argparse
        
        # This test verifies the argument parser configuration
        # by checking that the main function can be called without errors
        # when we mock the actual execution
        with patch("bot.run_v2.run_daily_digest") as mock_run:
            with patch("bot.run_v2.argparse.ArgumentParser") as mock_parser_class:
                mock_parser = Mock()
                mock_args = Mock()
                mock_args.mode = "daily"
                mock_args.hours = 24
                mock_args.channel = "test_channel"
                mock_args.dry_run = False
                mock_args.port = 8000
                mock_parser.parse_args.return_value = mock_args
                mock_parser_class.return_value = mock_parser
                
                # This should not raise an exception
                main()
                
                # Verify parser was created with correct description
                mock_parser_class.assert_called_once_with(
                    description="LobbyLens v2 - Enhanced Government Signals Bot"
                )
                
                # Verify arguments were added
                assert mock_parser.add_argument.call_count >= 5  # At least 5 arguments
