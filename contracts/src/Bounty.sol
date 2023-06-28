// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "./VerifierBase.sol";

contract Bounty {

    address public admin;
    // EZKL verifier
    Verifier public verifier;
    constructor(Verifier _verifier, address _admin) payable {
        if ( _verifier == Verifier(address(0)) || _admin == address(0) ) {
            revert();
        }
        verifier = _verifier;
        admin = _admin;
    }  

    function claimBounty(uint256[] memory pubInputs, bytes memory proof) public {
        // Verify EZKL proof.
        require(msg.sender != admin);
        require(verifier.verify(pubInputs, proof));
        // Send the bounty to the sender.
        (bool success, ) = msg.sender.call{value: address(this).balance}("");
        require(success);
        //payable(msg.sender).transfer(address(this).balance);
    }

    function updateVerifier(address _verifier) public payable {
        // Called when a new cycle occurs. The admin will update the verifier to the new one.
        require(msg.sender == admin);
        require(_verifier != address(0));
        verifier = Verifier(_verifier);
    }

}
