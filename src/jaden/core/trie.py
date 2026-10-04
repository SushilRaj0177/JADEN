"""JADEN: High-performance Trie for prefix matching across Japanese administrative entities.

Provides O(L) longest-prefix lookups where L is string prefix length,
independent of dictionary size N.
"""

from typing import Generic, TypeVar, Optional, Dict, Tuple, List

T = TypeVar("T")


class TrieNode(Generic[T]):
    """A single node within the PrefixTrie."""
    __slots__ = ("children", "value", "is_terminal")

    def __init__(self) -> None:
        self.children: Dict[str, TrieNode[T]] = {}
        self.value: Optional[T] = None
        self.is_terminal: bool = False


class PrefixTrie(Generic[T]):
    """High-performance Prefix Trie specialized for Japanese character string matching."""

    def __init__(self) -> None:
        self.root: TrieNode[T] = TrieNode[T]()
        self._count: int = 0

    def insert(self, key: str, value: T) -> None:
        """Inserts a key-value mapping into the Trie.

        Args:
            key: Japanese string key (e.g., '東京都', '横浜市中区').
            value: Associated metadata record.
        """
        if not key:
            return

        node = self.root
        for char in key:
            if char not in node.children:
                node.children[char] = TrieNode[T]()
            node = node.children[char]

        if not node.is_terminal:
            self._count += 1
        node.is_terminal = True
        node.value = value

    def search_exact(self, key: str) -> Optional[T]:
        """Performs exact key lookup."""
        node = self.root
        for char in key:
            if char not in node.children:
                return None
            node = node.children[char]
        return node.value if node.is_terminal else None

    def longest_prefix(self, text: str, start_index: int = 0) -> Optional[Tuple[str, T, int]]:
        """Finds the longest matching key in the Trie that forms a prefix of text[start_index:].

        Args:
            text: Input string.
            start_index: Starting offset to begin prefix matching.

        Returns:
            Tuple of (matched_key, value, next_index) or None if no prefix matches.
        """
        node = self.root
        last_match: Optional[Tuple[str, T, int]] = None
        idx = start_index
        text_len = len(text)

        while idx < text_len:
            char = text[idx]
            if char not in node.children:
                break
            node = node.children[char]
            idx += 1
            if node.is_terminal and node.value is not None:
                last_match = (text[start_index:idx], node.value, idx)

        return last_match

    def __len__(self) -> int:
        return self._count
