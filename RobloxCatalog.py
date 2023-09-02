import os
import requests
import json
from time import sleep, strftime, time


nextPageCursor = ""
items = []
basePath = os.path.dirname(os.path.abspath(__file__))
cookieRBLXSEC = open(f"{basePath}\\RS.token", "r").read()
xcsrfToken = None

expectedPriceLimit = 0 # just in case anything terrible happens, it limits purchasing price!
requestMaxRequestsRateLimit = 60 # How many requests per minute, maximum?
purchaseRateLimitCooldown = 5

arguments = f"category=All&limit=120&maxPrice={expectedPriceLimit}&minPrice=0&salesTypeFilter=1"#f"Category=CurrencyType=3&limit=120&maxPrice={expectedPriceLimit}&minPrice=0&SortType=3&salesTypeFilter=1"

# Class
## for loop accessible alternative
## Source: https://stackoverflow.com/questions/55380989#answer-55381187
class PositionableSequenceIterator:
    '''
    Custom for loop to be able to revert back when errors occur,
    such as rate limiting, so products on search page never get
    skipped when rate limited.
    '''


    def __init__(self, sequence):
        self.seq = sequence
        self._nextpos = 0

    @property
    def pos(self):
        pos = self._nextpos
        return 0 if pos is None else pos - 1

    @pos.setter
    def pos(self, newpos):
        if not 0 <= newpos < len(self.seq):
            raise IndexError(newpos)
        self._nextpos = newpos

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return self.seq[self._nextpos or 0]
        except IndexError:
            raise StopIteration
        finally:
            self._nextpos += 1

# Functions

def getXCRFTOKEN() -> str:
    '''
    Returns the x-crsf-token with .ROBLOXSECURITY via auth.roblox.com/v1/logout endpoint.
    It doesn't logout as the name indicates.
    '''


    global xcsrfToken
    #GETTING XSRF TOKEN
    if not xcsrfToken:
        xcsrfToken = requests.post(
            "https://auth.roblox.com/v1/logout",
            headers = {
                "cookie": f".ROBLOSECURITY={cookieRBLXSEC}"
            }
        ).headers["x-csrf-token"]

    return xcsrfToken

def getProductDetails(id: int, productType: str = "Asset") -> dict:
    '''
    * id can be any asset
    * productType can be Asset or Bundle, depending on the type of id provided,
    and also you can get the productType from itemType in their details.

    https://catalog.roblox.com/v1/catalog/items/{id}/details?itemType=Asset
    and uses both .ROBLOXSECURITY and X-CSRF-TOKEN to prevent code 0 error, too many requests
    '''
    

    request = requests.get(
        url=f"https://catalog.roblox.com/v1/catalog/items/{id}/details?itemType={productType}", # itemType=Asset/Bundle
        cookies={
            ".ROBLOSECURITY": cookieRBLXSEC,
        },
        headers={
            "X-CSRF-TOKEN": getXCRFTOKEN()
        }
    )

    return json.loads(request.content)

def organizer():
    '''
    Looks up all items within the arguments of the search and after
    collecting all items in page, goes to the next page via nextPageCursor.

    If nextPageCursor couldn't be found, this indicates that the search
    has been finished, which throws everything collected into the items
    list into the json file at the end of the file.

    Afterward the purchaseAsset function can be used to purchase any
    item included into the json file with productId to differeniate
    between any item published in Roblox, and creatorTargetId to make
    sure the creator of the asset is the same when purchase is happening,
    and finally the expectedPrice parameter to make sure the purchase
    price is the same as the client expects.
    And all of those paramters are necessary as they're included into the
    payload, but the productId which clearly indicates that it is needed
    to know what to post purchase.
    '''
    

    global nextPageCursor

    request = requests.get(
        url=f"https://catalog.roblox.com/v1/search/items?{arguments}{'' if not nextPageCursor else f'&cursor={nextPageCursor}'}"
    ) ## Gets raw catalog page items

    catalogJSON = json.loads(request.content)
    iterator = PositionableSequenceIterator(catalogJSON["data"])
    stepBack = False

    # Unix Timestamp to effectively cooldown requests: 60 requests / minute
    startResultCollectingOnPage = int(time())

    for item in iterator:
        print(iterator.pos)
        # input(item)
        itemDetails = getProductDetails(id=item["id"], productType=item["itemType"])
        print(f"[{strftime('%H:%M:%S')}]: {itemDetails}")
        
        if not itemDetails.get("errors"):
            if stepBack:
                stepBack = False
                print(iterator.pos)
                iterator.pos = 0 if iterator.pos <= 2 else iterator.pos - 2 # To get back 1 step and complete the ratelimit'd asset
                continue
            
            if not itemDetails["owned"] and itemDetails["isPurchasable"] and itemDetails["price"] <= expectedPriceLimit:
                # print(itemDetails)
                if str(itemDetails["offSaleDeadline"]) != "None": # prioritizes offsaleDeadline products
                    items.insert(0, {"productId": itemDetails["productId"],"creatorTargetId": itemDetails["creatorTargetId"],"expectedPrice": itemDetails["price"]})#item["id"])
                else:
                    # print(itemDetails)
                    # print(itemDetails["productId"])
                    # input()
                    items.append({"productId": itemDetails["productId"],"creatorTargetId": itemDetails["creatorTargetId"],"expectedPrice": itemDetails["price"]})#item["id"])
        else:
            cooldownCalculation = startResultCollectingOnPage + requestMaxRequestsRateLimit - int(time())
            cooldown = cooldownCalculation if cooldownCalculation > 0 else 5 # 5 seconds cooldown if requesting is exceeded to prevent further issues
            print(f"[{strftime('%H:%M:%S')}]: rate limit cooldown, {cooldown} seconds.")
            sleep(cooldown)
            stepBack = True
        
        # if iterator.pos > 4:
        #     nextPageCursor = None
        #     break
    
    nextPageCursor = catalogJSON["nextPageCursor"] # if not NoneValue, the function will be called again with next page

def purchaseAsset(productId: int, creatorTargetId: int, expectedPrice: int, expectedCurrency: int = 1):
    '''
    * productId: Asset's Product Id, not any id.
    * creatorTargetId: The asset's creator id.
    * expectedPrice: To make sure the client's price is the same as the server's.
    [optional] expectedCurrency: Payment currency Robux = 1.
    '''
    

    # xsrfRequest = requests.post(authurl, cookies={ #GETTING XSRF TOKEN
    #     '.ROBLOSECURITY': cookieRBLXSEC
    # })

    # buyRequest = requests.post( #BUYING THE ITEM
    #     "https://economy.roblox.com/v1/purchases/products/" + str(productid),
    #     cookies={'.ROBLOSECURITY': cookieRBLXSEC}, data={"expectedCurrency": 1, "expectedPrice": seller['price'],
    #         "expectedSellerId": seller['seller']['id']}, headers={
    #         "X-CSRF-TOKEN": xsrfRequest.headers["x-csrf-token"],
    #         "Content-Type": "application/json ; charset=utf-8"
    #     }
    # )

    # ty https://devforum.roblox.com/t/569144/10?u=roblox
    # getting token

    headers = {
        "cookie": f".ROBLOSECURITY={cookieRBLXSEC}",
        "x-csrf-token": getXCRFTOKEN(),
        "content-type": "application/json"
    }

    # getting asset details

    payload = {
        "expectedSellerId": creatorTargetId,
        "expectedCurrency": expectedCurrency, # 1 = robux
        "expectedPrice": expectedPrice
    }

    # buying item

    if expectedPrice <= expectedPriceLimit:
        buyRequest = requests.post(f"https://economy.roblox.com/v1/purchases/products/{productId}", headers = headers, data = json.dumps(payload))
        print(buyRequest.json())
        print(f"[{strftime('%H:%M:%S')}]: purchase rate limit cooldown, {purchaseRateLimitCooldown} seconds.")
        sleep(purchaseRateLimitCooldown)
    else:
        input(f"WARNING: price limit exceeded for {productId}\nExpected lower than {expectedPriceLimit}, but found {expectedPrice}.")




input("proceed to organizer?")
# Gets all products in search results
while nextPageCursor != None:# and not keyboard.is_pressed("esc"): # For early dev debugging
    organizer()

# Write and prettify search result in JSON
open(f"{basePath}\\results.json", "w").write(json.dumps(items, indent=4))

input("start purchasing?")

# Iterates search results and purchases them after conditional checks
for item in items:
    print(item["productId"], item["creatorTargetId"], item["expectedPrice"])
    input("next purchase?") 
    purchaseAsset(item["productId"], item["creatorTargetId"], item["expectedPrice"])
