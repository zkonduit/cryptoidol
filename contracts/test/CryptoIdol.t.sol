// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.17;

import "forge-std/Test.sol";
import "../src/VerifierBase.sol";
import "../src/CryptoIdol.sol";
import "../src/Bounty.sol";

contract CryptoIdolTest is Test {
    CryptoIdol public cryptoIdol;
    Verifier public verifier;
    Bounty public bounty;


    function setUp() public {
        verifier = new Verifier();
        cryptoIdol = new CryptoIdol(verifier, address(this));
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

    function testSubmitScore() public {
        // Success case, this account
        uint256[] memory publicInputs = new uint256[](2);
        publicInputs[0] = 2; // score
        string[] memory inputs = new string[](1);
        inputs[0] = "./scripts/fetch_proof.sh";
        bytes memory proof = vm.ffi(inputs); 
        // Check that the NewEntry event was emitted correctly
        vm.expectEmit(address(cryptoIdol));
        emit NewEntry(address(this), 2, 1);
        cryptoIdol.submitScore(publicInputs, proof);
        // Check that the scores mapping was updated correctly
        (uint score, uint cycle) = cryptoIdol.contestants(address(this));
        assertEq(score, publicInputs[0]);
        assertEq(cycle, 1);
    }

    function testUpdateVerifier(address account) public {
        vm.assume(account != address(this));
        verifier = new Verifier();
        vm.expectEmit(address(cryptoIdol));
        emit NewCycle(address(verifier), 2);
        cryptoIdol.updateVerifier(address(verifier));
        assert(cryptoIdol.verifier() == verifier);
        assertEq(cryptoIdol.cycle(), 2);
        // Should fail if non admin account tries to update the verifier
        vm.prank(account);
        vm.expectRevert();
        cryptoIdol.updateVerifier(address(verifier));
        vm.expectRevert();
        cryptoIdol.updateVerifier(address(0));
    }
}
