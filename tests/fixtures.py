RSS_FEED = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>Example World</title>
    <link>https://example.com/world</link>
    <description>World news</description>
    <item>
      <guid>article-1</guid>
      <title>First story</title>
      <link>https://example.com/news/1?utm_source=feed&amp;gclid=abc</link>
      <author>Reporter One</author>
      <pubDate>Mon, 01 Jun 2026 10:00:00 GMT</pubDate>
      <description><![CDATA[First summary]]></description>
    </item>
    <item>
      <guid>article-2</guid>
      <link>https://example.com/news/2&#x0A;?utm_campaign=x</link>
      <description><![CDATA[Second summary]]></description>
    </item>
    <item>
      <guid>drop-me</guid>
      <description><![CDATA[No title and no URL]]></description>
    </item>
  </channel>
</rss>
"""

RSS_FEED_UPDATED = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
  <channel>
    <title>Example World</title>
    <link>https://example.com/world</link>
    <description>World news</description>
    <item>
      <guid>article-1</guid>
      <title>First story updated</title>
      <link>https://example.com/news/1?utm_medium=social</link>
      <author>Reporter One</author>
      <pubDate>Mon, 01 Jun 2026 10:00:00 GMT</pubDate>
      <description><![CDATA[First summary updated]]></description>
    </item>
  </channel>
</rss>
"""
