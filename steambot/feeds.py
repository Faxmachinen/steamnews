import dateutil.parser
import requests
import xml.etree.ElementTree as ET

def getChildTextOrNone(tag, child):
	if tag is None:
		return None
	child_tag = tag.find(child)
	if child_tag is None:
		return None
	return child_tag.text

class NewsItem:
	@classmethod
	def from_tag(Cls, item_tag):
		title = getChildTextOrNone(item_tag, 'title')
		link = getChildTextOrNone(item_tag, 'link')
		description = getChildTextOrNone(item_tag, 'description')
		date_text = getChildTextOrNone(item_tag, 'pubDate')
		date = dateutil.parser.parse(date_text)
		return Cls(title, link, description, date)
	def __init__(self, title, link, description, date):
		self.title = title
		self.link = link
		self.description = description
		self.date = date
	def __lt__(self, other):
		return self.timestamp() < other.timestamp()
	def timestamp(self):
		if self.date is None:
			return 0
		else:
			return self.date.timestamp()
	def format_date(self):
		if self.date is None:
			return ""
		else:
			return self.date.strftime("%A, %B %d at %H:%M:%S %Z")

def load(app_id, config, log):
	url = config['steam_feed_url'].format(id=app_id)
	r = requests.get(url)
	if 200 <= r.status_code < 300:
		return parse(r.text)
	else:
		log.warning(f"Code {r.status_code} when fetching {url}")
		return None

def parse(rss):
	root = ET.fromstring(rss)
	item_tags = root.findall('channel/item')
	return sorted([NewsItem.from_tag(tag) for tag in item_tags])

def items_after(items, timestamp):
	return [x for x in items if x.timestamp() > timestamp]
