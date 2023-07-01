// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "./VerifierBase.sol";

contract Bounty {

    address public immutable admin;
    // EZKL verifier
    Verifier public verifier;

    receive() external payable {}

    constructor(Verifier _verifier, address _admin) payable {
        verifier = _verifier;
        admin = _admin;
    }  

    function claimBounty(uint256[] memory pubInputs, bytes memory proof) public {
        // Verify EZKL proof.
        require(msg.sender != admin);
        require(verifier.verify(pubInputs, proof));
        // Send the bounty to the sender.
        (bool success, ) =  address(uint160(pubInputs[0])).call{value: address(this).balance}("");
        require(success);
    }

    function updateVerifier(address _verifier) public payable {
        // Called when a new cycle occurs. The admin will update the verifier to the new one.
        require(msg.sender == admin);
        require(_verifier != address(0));
        verifier = Verifier(_verifier);
    }

    function withdraw() public {
        require(msg.sender == admin);
        (bool success, ) = msg.sender.call{value: address(this).balance}("");
        require(success);
    }

}
