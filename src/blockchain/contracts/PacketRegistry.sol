// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/// @title PacketRegistry
/// @notice On-chain anchor for packet fingerprints. This is the OPTIONAL Ethereum
///         variant of PacketGuard's local chain: deploy it to a testnet (e.g.
///         Ganache) and have the sender write each packet's SHA-256 hash here
///         before transmission. The receiver then reads the anchor back and
///         compares it against what actually arrived.
/// @dev    Hashes are stored as bytes32. The contract is deliberately minimal —
///         integrity logic lives off-chain in the Python engine; the chain only
///         provides the immutable, tamper-evident record.
contract PacketRegistry {
    struct Anchor {
        bytes32 packetHash;   // SHA-256 of the packet payload
        uint64  timestamp;    // block time when anchored
        address sender;       // who anchored it
        bool    exists;
    }

    /// @dev sequence number => anchor
    mapping(uint256 => Anchor) private anchors;

    /// @dev payload hash => first sequence that used it (for replay detection)
    mapping(bytes32 => uint256) private firstSeen;

    uint256 public totalAnchored;

    event PacketAnchored(uint256 indexed seq, bytes32 indexed packetHash, address sender);
    event ReplayObserved(uint256 indexed seq, bytes32 indexed packetHash, uint256 firstSeq);

    /// @notice Anchor a single packet hash under a sequence number.
    /// @dev Reverts if the sequence number was already anchored (anchors are immutable).
    function anchorPacket(uint256 seq, bytes32 packetHash) external {
        require(!anchors[seq].exists, "seq already anchored");

        anchors[seq] = Anchor({
            packetHash: packetHash,
            timestamp: uint64(block.timestamp),
            sender: msg.sender,
            exists: true
        });
        totalAnchored += 1;

        uint256 priorSeq = firstSeen[packetHash];
        if (priorSeq != 0 || _isGenesisHashSeen(packetHash)) {
            emit ReplayObserved(seq, packetHash, priorSeq);
        } else {
            firstSeen[packetHash] = seq;
        }

        emit PacketAnchored(seq, packetHash, msg.sender);
    }

    /// @notice Batch-anchor many packets in one transaction (gas-efficient).
    function anchorBatch(uint256[] calldata seqs, bytes32[] calldata hashes) external {
        require(seqs.length == hashes.length, "length mismatch");
        for (uint256 i = 0; i < seqs.length; i++) {
            require(!anchors[seqs[i]].exists, "seq already anchored");
            anchors[seqs[i]] = Anchor({
                packetHash: hashes[i],
                timestamp: uint64(block.timestamp),
                sender: msg.sender,
                exists: true
            });
            emit PacketAnchored(seqs[i], hashes[i], msg.sender);
        }
        totalAnchored += seqs.length;
    }

    /// @notice Verify an arrived packet against its anchor.
    /// @return status 0 = verified, 1 = tampered, 2 = unknown (no anchor).
    function verifyPacket(uint256 seq, bytes32 actualHash)
        external
        view
        returns (uint8 status)
    {
        Anchor memory a = anchors[seq];
        if (!a.exists) return 2;
        return a.packetHash == actualHash ? 0 : 1;
    }

    /// @notice Read a stored anchor.
    function getAnchor(uint256 seq)
        external
        view
        returns (bytes32 packetHash, uint64 timestamp, address sender, bool exists)
    {
        Anchor memory a = anchors[seq];
        return (a.packetHash, a.timestamp, a.sender, a.exists);
    }

    function _isGenesisHashSeen(bytes32 packetHash) private view returns (bool) {
        // firstSeen maps to seq 0 only if seq 0 anchored this hash.
        return anchors[0].exists && anchors[0].packetHash == packetHash;
    }
}
