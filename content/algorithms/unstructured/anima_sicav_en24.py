"""ANIMA_SICAV-EN24 format submodule"""

import re
from freeports.interfaces.pdf_blks import ResultStandardExtraction
from freeports.standard_funcs.text_filter import TextFilterInvestmentsStandard
from freeports.interfaces.text_blks import ResultStandardFiltering
from freeports.core import Pipeline

market_value_regex = re.compile(r"(([0-9]+,)?[0-9]+,?[0-9]+\.[0-9]{2}) ")
# non sono sicuro di come ho riscritto questa regex e a cosa servivano le parentesi

std = TextFilterInvestmentsStandard(
    nominal_quantity_pos=0,
    perc_net_assets_pos=3,
    acquisition_currency_pos=1,
    market_value_pos=2,
)

fund_remove_regex=re.compile(r"\(in .+\)")
def text_filter(pdf_blks, target_companies):
    """
    Text extract that extract quantity from the name of the company (is conained in the same cell)
    """
    txt_blks = std(pdf_blks, target_companies)
    for txt_blk in txt_blks:
        if txt_blk.type_block==ResultStandardFiltering.FUND.name:
            txt_blk.content=fund_remove_regex.sub("",txt_blk.content).replace("*","")
            continue
        c = txt_blk.content
        m = market_value_regex.match(c)
        txt_blk.metadata |= {
            "quantity": m[0],
        }
        txt_blk.metadata["fund"]=fund_remove_regex.sub("",txt_blk.metadata["fund"]).replace("*","")
    return txt_blks


pipelines = {"investments": Pipeline(text_filter=text_filter)}
