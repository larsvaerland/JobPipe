"""Unit tests for FINN related-jobs extraction in pull_suggested.py."""
from __future__ import annotations

import json

import pytest

# Skip if beautifulsoup4 is not installed (optional dependency)
bs4 = pytest.importorskip("bs4", reason="beautifulsoup4 not installed")
from bs4 import BeautifulSoup

from jobpipe.cli.pull_suggested import _extract_finn_related_finnkodes


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def test_extracts_finnkodes_from_href():
    html = """
    <html><body>
      <a href="/job/fulltime/ad.html?finnkode=111111">Job A</a>
      <a href="/job/fulltime/ad.html?finnkode=222222">Job B</a>
      <a href="https://www.finn.no/job/parttime/ad.html?finnkode=333333">Job C</a>
    </body></html>
    """
    result = _extract_finn_related_finnkodes(_soup(html), current_finnkode="999999")
    assert "111111" in result
    assert "222222" in result
    assert "333333" in result
    assert "999999" not in result  # current job excluded


def test_excludes_current_finnkode():
    html = """
    <html><body>
      <a href="/job/fulltime/ad.html?finnkode=123456">Current job (should be excluded)</a>
      <a href="/job/fulltime/ad.html?finnkode=654321">Other job</a>
    </body></html>
    """
    result = _extract_finn_related_finnkodes(_soup(html), current_finnkode="123456")
    assert "123456" not in result
    assert "654321" in result


def test_extracts_from_next_data_recommendations():
    recommendations = [
        {"finnkode": "777777", "title": "Related Job A"},
        {"finnkode": "888888", "title": "Related Job B"},
        {"id": "999001", "title": "Related Job C (id field)"},
    ]
    next_data = {
        "props": {
            "pageProps": {
                "recommendations": recommendations,
            }
        }
    }
    html = f"""
    <html><head>
      <script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>
    </head><body></body></html>
    """
    result = _extract_finn_related_finnkodes(_soup(html), current_finnkode="000000")
    assert "777777" in result
    assert "888888" in result
    assert "999001" in result


def test_deduplicates_across_strategies():
    """Same finnkode from both href and Next.js data should appear only once."""
    next_data = {
        "props": {"pageProps": {"similarAds": [{"finnkode": "111111"}]}}
    }
    html = f"""
    <html><head>
      <script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>
    </head><body>
      <a href="/job/fulltime/ad.html?finnkode=111111">Duplicate</a>
      <a href="/job/fulltime/ad.html?finnkode=222222">Unique</a>
    </body></html>
    """
    result = _extract_finn_related_finnkodes(_soup(html), current_finnkode="000000")
    assert result.count("111111") == 1
    assert "222222" in result


def test_returns_empty_for_no_links():
    html = "<html><body><p>No job links here.</p></body></html>"
    result = _extract_finn_related_finnkodes(_soup(html), current_finnkode="000000")
    assert result == []


def test_ignores_non_job_finn_links():
    html = """
    <html><body>
      <a href="/eiendom/ad.html?finnkode=111111">Not a job</a>
      <a href="/job/fulltime/ad.html?finnkode=222222">This is a job</a>
    </body></html>
    """
    result = _extract_finn_related_finnkodes(_soup(html), current_finnkode="000000")
    assert "111111" not in result
    assert "222222" in result
