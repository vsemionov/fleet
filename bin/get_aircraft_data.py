#!/usr/bin/env python

from pathlib import Path
from typing import Union, Optional

import click
import requests
from tqdm import tqdm
from pyspark.sql import SparkSession


def download(url: str, save_path: Union[Path, str], desc: Optional[str] = None):
    block_size = 32 * 1024
    desc = desc or save_path.name
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, timeout=30, stream=True) as response:
        response.raise_for_status()
        total = int(response.headers.get('content-length', 0))
        with open(save_path, 'wb') as file, \
                tqdm(desc=desc, total=total, unit='B', unit_scale=True) as pbar:
            for data in response.iter_content(block_size):
                size = file.write(data)
                pbar.update(size)


@click.command()
@click.argument('url')
@click.argument('path', type=click.Path(dir_okay=False, path_type=Path))
def main(url, path):
    download(url, path)

    spark = SparkSession.builder.getOrCreate()

    df = spark.read.csv(str(path), header=True, inferSchema=True, escape="'", quote="'")

    for col, dtype in df.dtypes:
        if dtype in ['date', 'timestamp']:
            df = df.withColumn(col, df[col].cast('string'))

    df.repartition(1).write.mode('overwrite').parquet(str(path.with_suffix('.parquet')))

    print('Success')


if __name__ == "__main__":
    main()
