#!/usr/bin/env python3


import sys
import argparse
import asyncio
import telepot.async as telepot_async
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor


class Reader:
    def __init__(self, loop, stream):
        self._loop = loop
        self._stream = stream
        self._executor = ThreadPoolExecutor()

    async def __aiter__(self):
        return self

    async def __anext__(self):
        line = await self.readline()
        if line == "":
            raise StopAsyncIteration
        return line

    async def readline(self):
        return await self._loop.run_in_executor(self._executor,
                                                self._stream.readline)

    async def read(self):
        return await self._loop.run_in_executor(self._executor,
                                                self._stream.read)


def parse_command_line():
    parser = argparse.ArgumentParser(description="Redirects stdin to a "
                                                 "Telegram channel or chat.")
    parser.add_argument("token", help="API token of the Telegram bot")
    parser.add_argument("channel", help="Chat ID or channel for broadcasts")
    parser.add_argument("-m", "--parse-mode", help="How the input should be "
                                                   "parsed",
                        choices=("HTML", "Markdown"))
    parser.add_argument("-s", "--split-newlines", help="If specified, each "
                                                       "input line will be "
                                                       "send as an individual "
                                                       "message",
                        action="store_true")

    return parser.parse_args()


async def transfer_stdin(loop, args):
    reader = Reader(loop, sys.stdin)
    bot = telepot_async.Bot(args.token, loop=loop)

    # If we don't need line-by-line output, go the easy way
    if not args.split_newlines:
        await bot.sendMessage(args.channel,
                              await reader.read(),
                              parse_mode=args.parse_mode)
        return

    # Go the hard way
    async for line in reader:
        await bot.sendMessage(args.channel, line, parse_mode=args.parse_mode)


def main():
    args = parse_command_line()

    with closing(asyncio.get_event_loop()) as loop:
        loop.run_until_complete(transfer_stdin(loop, args))


if __name__ == "__main__":
    main()
