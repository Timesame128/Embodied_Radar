from embodied_arxiv.arxiv_client import ArxivClient


SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>https://arxiv.org/abs/2606.12345v1</id>
    <updated>2026-06-10T00:00:00Z</updated>
    <published>2026-06-10T00:00:00Z</published>
    <title>Embodied Agent Test</title>
    <summary>A robot project at https://example.github.io/project.</summary>
    <author><name>Ada Example</name></author>
    <category term="cs.RO"/>
    <arxiv:primary_category term="cs.RO"/>
    <link href="https://arxiv.org/pdf/2606.12345v1" title="pdf"/>
  </entry>
</feed>"""


def test_parse_atom_feed():
    paper = ArxivClient.parse(SAMPLE)[0]
    assert paper["id"] == "2606.12345v1"
    assert paper["authors"] == ["Ada Example"]
    assert paper["primary_category"] == "cs.RO"
    assert paper["external_urls"] == ["https://example.github.io/project"]

