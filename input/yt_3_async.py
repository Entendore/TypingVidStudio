import asyncio

async def fetch_data(id: int) -> str:
    print(f"Fetching data {id}...")
    await asyncio.sleep(2)
    return f"Data_{id}"

async def main():
    tasks = [fetch_data(i) for i in range(3)]
    results = await asyncio.gather(*tasks)
    print(results)

asyncio.run(main())
