// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.17;

import "forge-std/Test.sol";
import "../src/VerifierBase.sol";
import "../src/Bounty.sol";

contract BountyTest is Test {
    Verifier public verifier;
    Bounty public bounty;

    function setUp() public {
        verifier = new Verifier();
        bounty = new Bounty{value: 1 ether}(verifier, address(this));
    }

    function testBounty(address account) public {
        vm.assume(account != address(this) && account != address(bounty));
        vm.assume(account != address(0) && account != address(verifier));
        vm.assume(account != 0x7109709ECfa91a80626fF3989D68f67F5b1DD12D);
        uint256[] memory publicInputs = new uint256[](2);
        publicInputs[0] = uint160(bytes20(account)); // addr to send bounty too
        publicInputs[1] = 2; // score
        string[] memory inputs = new string[](1);
        inputs[0] = "./scripts/fetch_proof.sh";
        bytes memory proof = vm.ffi(inputs); 
        // Should fail if admin calls claimBounty
        vm.expectRevert();
        bounty.claimBounty(publicInputs, proof);
        vm.prank(account);
        uint preBalance = account.balance;
        // Should succeed if non admin calls claimBounty
        bounty.claimBounty(publicInputs, proof);
        // Check that the bounty was sent to the sender
        assertEq(account.balance, preBalance + 1 ether);
    }
    function testUpdateVerifier(address account) public {
        vm.assume(account != address(this) && account != address(bounty) && account != address(0));
        verifier = new Verifier();
        bounty.updateVerifier(address(verifier));
        assert(bounty.verifier() == verifier);
        // Should fail if non admin account tries to update the verifier
        vm.prank(account);
        vm.expectRevert();
        bounty.updateVerifier(address(verifier));
        vm.expectRevert();
        bounty.updateVerifier(address(0));
    }

    function testWithdraw() public {
        // Should fail if non admin account tries to withdraw
        vm.prank(address(0));
        vm.expectRevert();
        bounty.withdraw();
        // Should succeed if admin calls withdraw
        uint prebalance = address(this).balance;
        bounty.withdraw();
        assertEq(address(this).balance, prebalance + 1 ether);
    }
    receive() external payable {}
}
