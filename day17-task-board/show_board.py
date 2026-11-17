"""Day 17: print the task board, without running any agents."""

import board

board.show()
print(f"\nWaiting: {board.count()}   Doing: {board.count(status='doing')}   "
      f"Done: {board.count(status='done')}")