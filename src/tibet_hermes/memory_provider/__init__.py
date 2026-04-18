"""TIBET Memory Provider for Hermes Agent.

Implements the MemoryProvider ABC — every memory write gets a TIBET token,
every memory read gets verified, everything is Bifurcation-sealed.
"""

from tibet_hermes.memory_provider.provider import TibetMemoryProvider
