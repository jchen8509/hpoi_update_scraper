import aiohttp
import asyncio
from bs4 import BeautifulSoup, Tag, ResultSet
from dataclasses import dataclass
from dotenv import load_dotenv
from enum import Enum
from hpoi_translation import Process
import os
import requests

load_dotenv()
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

login_link = "https://www.hpoi.net/user/login"
login_request = "https://www.hpoi.net/user/login/submit"
URL = "https://www.hpoi.net/"
wait_time_seconds: float = 60 * 5
BATCH_SIZE = 20

cookies = {
    'homeView': 'info',
    'allOrder': 'add',
    'utoken': os.getenv('UTOKEN') if(os.getenv('NSFW') == 1) else '',
}

class STATUS(Enum):
    NEW_ANNOUNCEMENT = "New Announcement"
    IMG_UPDATE = "Image Update"
    INFO_UPDATE = "Info Update"
    PO_OPENED = "Pre-Orders Opened"
    RELEASE_DATE = "Release Date"
    DELAYED = "Delayed"
    RE_RELEASE = "Re-Release"


# Chinese translations
TRANSLATIONS = {
    "Name": "名称",
    "Origin": "作品",
    "Character": "角色",
    "Manufacturer": "制作",
    "Illustrator": "原画",
    "Release Date": ["发售", "发售日"],
    "Price": "定价",
    "Material": "材质",
    "Scale": "比例",
    "Dimension": "尺寸",
    # --OUTER PAGE--
    "制作决定": STATUS.NEW_ANNOUNCEMENT,
    "官图更新": STATUS.IMG_UPDATE,
    "情报更新": STATUS.INFO_UPDATE,
    "预定时间": STATUS.PO_OPENED,
    "出荷时间": STATUS.RELEASE_DATE,
    "出荷延期": STATUS.DELAYED,
    "再版确定": STATUS.RE_RELEASE,
}

# TODO: add consts for selectors
@dataclass
class hpoiCard:
    # --OUTER PAGE--
    # card title
    title: str
    # update status
    status: STATUS
    # full link to item page
    link: str
    # image
    img_src: str

    # --INNER PAGE--
    name: str
    origin: str
    character: str
    manufacturer: str
    illustrator: str
    release_date: str
    price: str
    material: str
    scale: str
    dimension: str


async def tag_to_card(tag: Tag, session) -> hpoiCard:
    async with aiohttp.ClientSession() as session:
        # --OUTER PAGE--
        image: Tag = tag.find("div", class_="left-leioan").find("a")
        info: Tag = tag.find("div", class_="right-leioan")

        title: str = info.find_all("div")[4].text
        status: STATUS = TRANSLATIONS.get(info.find("div").find("span").text)
        # print(status)
        link: str = URL + "/" + image.get("href")
        img_src: str = image.find("img").get("src")

        # --INNER PAGE--
        res = await session.get(link)
        page = await res.read()
        inner_soup = BeautifulSoup(page, "html.parser")

        inner_info: Tag = inner_soup.find("div", class_="infoList-box")

        name = getItem(inner_info, TRANSLATIONS.get("Name"))
        # what does it take in = type
        # what variable it takes in = variable name

        origin = getItem(inner_info, TRANSLATIONS.get("Origin"))
        character = getItem(inner_info, TRANSLATIONS.get("Character"))

        manufacturer = getItem(inner_info, TRANSLATIONS.get("Manufacturer"))
        illustrator = getItem(inner_info, TRANSLATIONS.get("Illustrator"))
        release_date = getItem(inner_info, TRANSLATIONS.get("Release Date"))
        price = getItem(inner_info, TRANSLATIONS.get("Price"))
        material = getItem(inner_info, TRANSLATIONS.get("Material"))
        scale = getItem(inner_info, TRANSLATIONS.get("Scale"))
        dimension = getItem(inner_info, TRANSLATIONS.get("Dimension"))
        [
            translatedName,
            translatedOrigin,
            translatedCharacter,
            translatedManufacturer,
            translatedIllustrator,
            translatedReleaseDate,
            translatedPrice,
            translatedMaterial,
            translatedScale,
            translatedDimension,
        ] = await Process(
            session,
            sourceTexts=[
                name,
                origin,
                character,
                manufacturer,
                illustrator,
                release_date,
                price,
                material,
                scale,
                dimension,
            ],
        )
        return hpoiCard(
            title,
            status,
            link,
            img_src,
            translatedName,
            translatedOrigin,
            translatedCharacter,
            translatedManufacturer,
            translatedIllustrator,
            translatedReleaseDate,
            translatedPrice,
            translatedMaterial,
            translatedScale,
            translatedDimension,
        )


# Grabs text of info list item safely
def getItem(tag: Tag, infoList_name: str):
    try:
        return tag.find("span", string=infoList_name).findNext("p").text
    except AttributeError:
        # print(infoList_name + " not found")
        return ""


titleCache: list[str] = []


async def fetchCards() -> list[hpoiCard]:
    async with aiohttp.ClientSession() as session:
        # if(!cookies.get('utoken'))
        #     login
        res = await session.get(URL,cookies=cookies)

        text = await res.read()

        if res.status != 200:
            raise Exception("Website is down! Status code: " + res.status)

        print("Page loaded!")
        soup = BeautifulSoup(text, "html.parser")

        tags: ResultSet[Tag] = soup.find(
            "div", class_="hpoi-conter-ltsifrato"
        ).find_all("div", class_="hpoi-conter-left")

        tags = tags[:BATCH_SIZE]

        titles = map(
            lambda tag: tag.find("div", class_="right-leioan").find_all("div")[4].text,
            tags,
        )
        tags_and_titles = list(zip(tags, titles))

        tags_and_titles = list(
            filter(lambda pair: pair[1] not in titleCache, tags_and_titles)
        )
        if len(tags_and_titles) <= 0:
            print("Found no new cards!")
            return []
        print("Found " + str(len(tags_and_titles)) + " new cards!")

        cardTasks = []
        for tag, title in tags_and_titles:
            # Code to grab card data; make async tag_to_card
            cardTasks.insert(0, tag_to_card(tag, session))

            titleCache.insert(0, title)
            # Remove stale entries from cache
            # if len(titleCache) > BATCH_SIZE:
                # titleCache.pop(-1)
        cards = await asyncio.gather(*cardTasks)
    return cards

def login():
    # TODO convert to aiohttp
    with requests.Session() as s:

        payload = {}
        payload['email'] = username
        payload['password'] = password
        payload['MIME Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'

        s.post(login_request,data=payload)

        token = s.cookies.get('utoken')
        print(token)


if __name__ == "__main__":
    # Start the asyncio program
    # programming languages list
    asyncio.run(fetchCards())