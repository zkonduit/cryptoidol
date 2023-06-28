// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "./VerifierBase.sol";
import "./Bounty.sol";

contract CryptoIdol {

    struct Contestant {
        uint256 score;
        uint256 cycle;
    }

    event NewEntry (
        address contestant,
        uint256 score,
        uint256 cycle
    );

    event NewCycle (
        address verifier,
        uint256 cycle
    );

    // The mapping of all the scores for each contestant, as well as the hash of their song 
    // and cycle in which they participated.
    mapping(address => Contestant) public contestants;
    // The admin address in charge of updating the to new verifier each new cycle.
    address public admin;
    // The cycle number. This will be incremented by the admin each time a new cycle occurs.
    uint8 public cycle = 1;

    Verifier public verifier;
    constructor(Verifier _verifier, address _admin) {
        if ( _verifier == Verifier(address(0)) || _admin == address(0) ) {
            revert("No zero addresses");
        }
        verifier = _verifier;
        admin = _admin;
    }  

    function updateVerifier(address _verifier) public {
        // Called when a new cycle occurs. The admin will update the verifier to the new one.
        require(msg.sender == admin);
        require(_verifier != address(0));
        verifier = Verifier(_verifier);
        cycle += 1;
        emit NewCycle(address(verifier), cycle);
    }

    function submitScore(uint256[] memory pubInputs, bytes memory proof) public {
        // extract the song_hash and score from the public inputs
        uint256 score = pubInputs[0];
        // Verify EZKL proof.
        require(verifier.verify(pubInputs, proof));
        // Update the score struct
        contestants[msg.sender] = Contestant(score, cycle);
        // Emit the New Entry event. All of these events will be indexed on the client side in order
        // to construct the leaderboard as opposed to storing the entire leader board on the blockchain.
        emit NewEntry(msg.sender, score, cycle);
    }

}
