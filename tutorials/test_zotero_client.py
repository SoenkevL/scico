# %% initialize
from pprint import pprint

from src.zotero_client import ZoteroClient

client = ZoteroClient()


# %%
def seperator():
    print('=' * 100)


# %% basic info
print(client.get_item_count())

pprint(client.list_all_collections())

# %% search functionallity
pprint(client.get_items_by_collection_id("K7QSQYKD"))
seperator()

# %%
item = client.get_item_by_id("VK5V8ET7")
pprint(item)

# %%
pprint(client.get_items_by_collection_name("EEG_For_Meditation"))

# %%
pprint(client.get_item_by_id("YDI66MQF"))

# %%
pprint(client.get_items_by_name("EEG"))
