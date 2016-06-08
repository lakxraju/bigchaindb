import pytest
import time
import rethinkdb as r
import multiprocessing as mp

from bigchaindb import util

from bigchaindb.voter import Voter, Election, BlockStream
from bigchaindb import crypto, Bigchain


class TestBigchainVoter(object):

    def test_valid_block_voting(self, b):
        q_new_block = mp.Queue()

        genesis = b.create_genesis_block()

        # create valid block
        block = b.create_block([])
        # assert block is valid
        assert b.is_valid_block(block)
        b.write_block(block, durability='hard')

        # create queue and voter
        voter = Voter(q_new_block)

        # vote
        voter.start()
        # wait for vote to be written
        time.sleep(1)
        voter.kill()

        # retrive block from bigchain
        blocks = list(r.table('bigchain')
                       .order_by(r.asc((r.row['block']['timestamp'])))
                       .run(b.conn))

        # validate vote
        assert len(blocks[1]['votes']) == 1
        vote = blocks[1]['votes'][0]

        assert vote['vote']['voting_for_block'] == block['id']
        assert vote['vote']['previous_block'] == genesis['id']
        assert vote['vote']['is_block_valid'] is True
        assert vote['vote']['invalid_reason'] is None
        assert vote['node_pubkey'] == b.me
        assert crypto.VerifyingKey(b.me).verify(util.serialize(vote['vote']), vote['signature']) is True

    def test_valid_block_voting_with_create_transaction(self, b):
        q_new_block = mp.Queue()

        genesis = b.create_genesis_block()

        # create a `CREATE` transaction
        test_user_priv, test_user_pub = crypto.generate_key_pair()
        tx = b.create_transaction(b.me, test_user_pub, None, 'CREATE')
        tx_signed = b.sign_transaction(tx, b.me_private)
        assert b.is_valid_transaction(tx_signed)

        # create valid block
        block = b.create_block([tx_signed])
        # assert block is valid
        assert b.is_valid_block(block)
        b.write_block(block, durability='hard')

        # create queue and voter
        voter = Voter(q_new_block)

        # vote
        voter.start()
        # wait for vote to be written
        time.sleep(1)
        voter.kill()

        # retrive block from bigchain
        blocks = list(r.table('bigchain')
                       .order_by(r.asc((r.row['block']['timestamp'])))
                       .run(b.conn))

        # validate vote
        assert len(blocks[1]['votes']) == 1
        vote = blocks[1]['votes'][0]

        assert vote['vote']['voting_for_block'] == block['id']
        assert vote['vote']['previous_block'] == genesis['id']
        assert vote['vote']['is_block_valid'] is True
        assert vote['vote']['invalid_reason'] is None
        assert vote['node_pubkey'] == b.me
        assert crypto.VerifyingKey(b.me).verify(util.serialize(vote['vote']), vote['signature']) is True

    def test_valid_block_voting_with_transfer_transactions(self, b):
        q_new_block = mp.Queue()

        b.create_genesis_block()

        # create a `CREATE` transaction
        test_user_priv, test_user_pub = crypto.generate_key_pair()
        tx = b.create_transaction(b.me, test_user_pub, None, 'CREATE')
        tx_signed = b.sign_transaction(tx, b.me_private)
        assert b.is_valid_transaction(tx_signed)

        # create valid block
        block = b.create_block([tx_signed])
        # assert block is valid
        assert b.is_valid_block(block)
        b.write_block(block, durability='hard')

        # create queue and voter
        voter = Voter(q_new_block)

        # vote
        voter.start()
        # wait for vote to be written
        time.sleep(1)
        voter.kill()

        # retrive block from bigchain
        blocks = list(r.table('bigchain')
                       .order_by(r.asc((r.row['block']['timestamp'])))
                       .run(b.conn))

        # validate vote
        assert len(blocks[1]['votes']) == 1

        # create a `TRANSFER` transaction
        test_user2_priv, test_user2_pub = crypto.generate_key_pair()
        tx2 = b.create_transaction(test_user_pub, test_user2_pub, {'txid': {'/': tx['id']}, 'cid': 0}, 'TRANSFER')
        tx2_signed = b.sign_transaction(tx2, test_user_priv)
        assert b.is_valid_transaction(tx2_signed)

        # create valid block
        block = b.create_block([tx2_signed])
        # assert block is valid
        assert b.is_valid_block(block)
        b.write_block(block, durability='hard')

        # create queue and voter
        voter = Voter(q_new_block)

        # vote
        voter.start()
        # wait for vote to be written
        time.sleep(1)
        voter.kill()

        # retrive block from bigchain
        blocks = list(r.table('bigchain')
                       .order_by(r.asc((r.row['block']['timestamp'])))
                       .run(b.conn))

        # validate vote
        assert len(blocks[2]['votes']) == 1

        vote = blocks[2]['votes'][0]

        assert vote['vote']['voting_for_block'] == block['id']
        assert vote['vote']['is_block_valid'] is True
        assert vote['vote']['invalid_reason'] is None
        assert vote['node_pubkey'] == b.me
        assert crypto.VerifyingKey(b.me).verify(util.serialize(vote['vote']), vote['signature']) is True

    def test_invalid_block_voting(self, b, user_vk):
        # create queue and voter
        q_new_block = mp.Queue()
        voter = Voter(q_new_block)

        # create transaction
        transaction = b.create_transaction(b.me, user_vk, None, 'CREATE')
        transaction_signed = b.sign_transaction(transaction, b.me_private)

        genesis = b.create_genesis_block()

        # create invalid block
        block = b.create_block([transaction_signed])
        # change transaction id to make it invalid
        block['block']['transactions'][0]['id'] = 'abc'
        assert not b.is_valid_block(block)
        b.write_block(block, durability='hard')

        # vote
        voter.start()
        time.sleep(1)
        voter.kill()

        # retrive block from bigchain
        blocks = list(r.table('bigchain')
                       .order_by(r.asc((r.row['block']['timestamp'])))
                       .run(b.conn))

        # validate vote
        assert len(blocks[1]['votes']) == 1
        vote = blocks[1]['votes'][0]

        assert vote['vote']['voting_for_block'] == block['id']
        assert vote['vote']['previous_block'] == genesis['id']
        assert vote['vote']['is_block_valid'] is False
        assert vote['vote']['invalid_reason'] is None
        assert vote['node_pubkey'] == b.me
        assert crypto.VerifyingKey(b.me).verify(util.serialize(vote['vote']), vote['signature']) is True

    def test_vote_creation_valid(self, b):
        # create valid block
        block = b.create_block([])
        # retrieve vote
        vote = b.vote(block, 'abc', True)

        # assert vote is correct
        assert vote['vote']['voting_for_block'] == block['id']
        assert vote['vote']['previous_block'] == 'abc'
        assert vote['vote']['is_block_valid'] is True
        assert vote['vote']['invalid_reason'] is None
        assert vote['node_pubkey'] == b.me
        assert crypto.VerifyingKey(b.me).verify(util.serialize(vote['vote']), vote['signature']) is True

    def test_vote_creation_invalid(self, b):
        # create valid block
        block = b.create_block([])
        # retrieve vote
        vote = b.vote(block, 'abc', False)

        # assert vote is correct
        assert vote['vote']['voting_for_block'] == block['id']
        assert vote['vote']['previous_block'] == 'abc'
        assert vote['vote']['is_block_valid'] is False
        assert vote['vote']['invalid_reason'] is None
        assert vote['node_pubkey'] == b.me
        assert crypto.VerifyingKey(b.me).verify(util.serialize(vote['vote']), vote['signature']) is True

    def test_voter_considers_unvoted_blocks_when_single_node(self, b):
        # simulate a voter going donw in a single node environment
        b.create_genesis_block()

        # insert blocks in the database while the voter process is not listening
        # (these blocks won't appear in the changefeed)
        block_1 = b.create_block([])
        b.write_block(block_1, durability='hard')
        block_2 = b.create_block([])
        b.write_block(block_2, durability='hard')

        # voter is back online, we simulate that by creating a queue and a Voter instance
        q_new_block = mp.Queue()
        voter = Voter(q_new_block)

        # create a new block that will appear in the changefeed
        block_3 = b.create_block([])
        b.write_block(block_3, durability='hard')

        # put the last block in the queue
        q_new_block.put(block_3)

        # vote
        voter.start()
        time.sleep(1)
        voter.kill()

        # retrive blocks from bigchain
        blocks = list(r.table('bigchain')
                       .order_by(r.asc((r.row['block']['timestamp'])))
                       .run(b.conn))

        # FIXME: remove genesis block, we don't vote on it (might change in the future)
        blocks.pop(0)

        assert all(block['votes'][0]['node_pubkey'] == b.me for block in blocks)

    def test_voter_chains_blocks_with_the_previous_ones(self, b):
        b.create_genesis_block()
        block_1 = b.create_block([])
        b.write_block(block_1, durability='hard')
        block_2 = b.create_block([])
        b.write_block(block_2, durability='hard')

        q_new_block = mp.Queue()

        voter = Voter(q_new_block)
        voter.start()
        time.sleep(1)
        voter.kill()

        # retrive blocks from bigchain
        blocks = list(r.table('bigchain')
                       .order_by(r.asc((r.row['block']['timestamp'])))
                       .run(b.conn))

        assert blocks[0]['block_number'] == 0
        assert blocks[1]['block_number'] == 1
        assert blocks[2]['block_number'] == 2

        # we don't vote on the genesis block right now
        # assert blocks[0]['votes'][0]['vote']['voting_for_block'] == genesis['id']
        assert blocks[1]['votes'][0]['vote']['voting_for_block'] == block_1['id']
        assert blocks[2]['votes'][0]['vote']['voting_for_block'] == block_2['id']

    @pytest.mark.skipif(reason='Updating the block_number must be atomic')
    def test_updating_block_number_must_be_atomic(self):
        pass


class TestBlockElection(object):

    def test_quorum(self, b):
        # create a new block
        test_block = b.create_block([])

        # simulate a federation with four voters
        key_pairs = [crypto.generate_key_pair() for _ in range(4)]
        test_federation = [Bigchain(public_key=key_pair[1], private_key=key_pair[0])
                           for key_pair in key_pairs]

        # dummy block with test federation public keys as voters
        test_block['block']['voters'] = [key_pair[1] for key_pair in key_pairs]

        # fake "yes" votes
        valid_vote = [member.vote(test_block, 'abc', True)
                      for member in test_federation]

        # fake "no" votes
        invalid_vote = [member.vote(test_block, 'abc', False)
                        for member in test_federation]

        # fake "yes" votes with incorrect signatures
        improperly_signed_valid_vote = [member.vote(test_block, 'abc', True) for
                                        member in test_federation]
        [vote['vote'].update(this_should_ruin_things='lol')
         for vote in improperly_signed_valid_vote]

        # test unanimously valid block
        test_block['votes'] = valid_vote
        assert b.block_election_status(test_block) == Bigchain.BLOCK_VALID

        # test partial quorum situations
        test_block['votes'] = valid_vote[:2]
        assert b.block_election_status(test_block) == Bigchain.BLOCK_UNDECIDED
        #
        test_block['votes'] = valid_vote[:3]
        assert b.block_election_status(test_block) == Bigchain.BLOCK_VALID
        #
        test_block['votes'] = invalid_vote[:2]
        assert b.block_election_status(test_block) == Bigchain.BLOCK_INVALID

        # test unanimously valid block with one improperly signed vote -- should still succeed
        test_block['votes'] = valid_vote[:3] + improperly_signed_valid_vote[:1]
        assert b.block_election_status(test_block) == Bigchain.BLOCK_VALID

        # test unanimously valid block with two improperly signed votes -- should fail
        test_block['votes'] = valid_vote[:2] + improperly_signed_valid_vote[:2]
        assert b.block_election_status(test_block) == Bigchain.BLOCK_INVALID

        # test block with minority invalid vote
        test_block['votes'] = invalid_vote[:1] + valid_vote[:3]
        assert b.block_election_status(test_block) == Bigchain.BLOCK_VALID

        # test split vote
        test_block['votes'] = invalid_vote[:2] + valid_vote[:2]
        assert b.block_election_status(test_block) == Bigchain.BLOCK_INVALID

        # test undecided
        test_block['votes'] = valid_vote[:2]
        assert b.block_election_status(test_block) == Bigchain.BLOCK_UNDECIDED

        # change signatures in block, should fail
        test_block['block']['voters'][0] = 'abc'
        test_block['block']['voters'][1] = 'abc'
        test_block['votes'] = valid_vote
        assert b.block_election_status(test_block) == Bigchain.BLOCK_INVALID

    def test_quorum_odd(self, b):
        # test partial quorum situations for odd numbers of voters
        # create a new block
        test_block = b.create_block([])

        # simulate a federation with four voters
        key_pairs = [crypto.generate_key_pair() for _ in range(5)]
        test_federation = [Bigchain(public_key=key_pair[1], private_key=key_pair[0])
                           for key_pair in key_pairs]

        # dummy block with test federation public keys as voters
        test_block['block']['voters'] = [key_pair[1] for key_pair in key_pairs]

        # fake "yes" votes
        valid_vote = [member.vote(test_block, 'abc', True)
                      for member in test_federation]

        # fake "no" votes
        invalid_vote = [member.vote(test_block, 'abc', False)
                        for member in test_federation]

        test_block['votes'] = valid_vote[:2]
        assert b.block_election_status(test_block) == Bigchain.BLOCK_UNDECIDED

        test_block['votes'] = invalid_vote[:2]
        assert b.block_election_status(test_block) == Bigchain.BLOCK_UNDECIDED

        test_block['votes'] = valid_vote[:3]
        assert b.block_election_status(test_block) == Bigchain.BLOCK_VALID

        test_block['votes'] = invalid_vote[:3]
        assert b.block_election_status(test_block) == Bigchain.BLOCK_INVALID

    def test_tx_rewritten_after_invalid(self, b, user_vk):
        q_block_new_vote = mp.Queue()

        # create blocks with transactions
        tx1 = b.create_transaction(b.me, user_vk, None, 'CREATE')
        tx2 = b.create_transaction(b.me, user_vk, None, 'CREATE')
        test_block_1 = b.create_block([tx1])
        test_block_2 = b.create_block([tx2])

        # simulate a federation with four voters
        key_pairs = [crypto.generate_key_pair() for _ in range(4)]
        test_federation = [Bigchain(public_key=key_pair[1], private_key=key_pair[0])
                           for key_pair in key_pairs]

        # simulate a federation with four voters
        test_block_1['block']['voters'] = [key_pair[1] for key_pair in key_pairs]
        test_block_2['block']['voters'] = [key_pair[1] for key_pair in key_pairs]

        # votes for block one
        vote_1 = [member.vote(test_block_1, 'abc', True)
                      for member in test_federation]

        # votes for block two
        vote_2 = [member.vote(test_block_2, 'abc', True) for member in test_federation[:2]] + \
                       [member.vote(test_block_2, 'abc', False) for member in test_federation[2:]]

        # construct valid block
        test_block_1['votes'] = vote_1
        q_block_new_vote.put(test_block_1)

        # construct invalid block
        test_block_2['votes'] = vote_2
        q_block_new_vote.put(test_block_2)

        election = Election(q_block_new_vote)
        election.start()
        time.sleep(1)
        election.kill()

        # tx1 was in a valid block, and should not be in the backlog
        assert r.table('backlog').get(tx1['id']).run(b.conn) is None

        # tx2 was in an invalid block and SHOULD be in the backlog
        assert r.table('backlog').get(tx2['id']).run(b.conn)['id'] == tx2['id']


class TestBlockStream(object):

    def test_if_federation_size_is_greater_than_one_ignore_past_blocks(self, b):
        for _ in range(5):
            b.federation_nodes.append(crypto.generate_key_pair()[1])
        new_blocks = mp.Queue()
        bs = BlockStream(new_blocks)
        block_1 = b.create_block([])
        new_blocks.put(block_1)
        assert block_1 == bs.get()

    def test_if_no_old_blocks_get_should_return_new_blocks(self, b):
        new_blocks = mp.Queue()
        bs = BlockStream(new_blocks)

        # create two blocks
        block_1 = b.create_block([])
        block_2 = b.create_block([])

        # write the blocks
        b.write_block(block_1, durability='hard')
        b.write_block(block_2, durability='hard')

        # simulate a changefeed
        new_blocks.put(block_1)
        new_blocks.put(block_2)

        # and check if we get exactly these two blocks
        assert bs.get() == block_1
        assert bs.get() == block_2

    def test_if_old_blocks_get_should_return_old_block_first(self, b):
        # create two blocks
        block_1 = b.create_block([])
        block_2 = b.create_block([])

        # write the blocks
        b.write_block(block_1, durability='hard')
        b.write_block(block_2, durability='hard')

        new_blocks = mp.Queue()
        bs = BlockStream(new_blocks)

        # assert len(list(bs.old_blocks)) == 2
        # import pdb; pdb.set_trace()
        # from pprint import pprint as pp
        # pp(bs.old_blocks)
        # pp(block_1)
        # pp(block_2)

        # create two new blocks that will appear in the changefeed
        block_3 = b.create_block([])
        block_4 = b.create_block([])

        # simulate a changefeed
        new_blocks.put(block_3)
        new_blocks.put(block_4)

        assert len(bs.unvoted_blocks) == 2

        # and check if we get the old blocks first
        assert bs.get() == block_1
        assert bs.get() == block_2
        assert bs.get() == block_3
        assert bs.get() == block_4

    @pytest.mark.skipif(reason='We may have duplicated blocks when retrieving the BlockStream')
    def test_ignore_duplicated_blocks_when_retrieving_the_blockstream(self):
        pass
