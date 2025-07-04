from __future__ import annotations

import json
import random
from dataclasses import dataclass, replace
from typing import Callable, Optional

import importlib_resources
import pytest
from chia_rs import AugSchemeMPL, G1Element, PrivateKey
from chia_rs.sized_bytes import bytes32
from chia_rs.sized_ints import uint32

import chia._tests.util
from chia.simulator.keyring import TempKeyring
from chia.util.errors import (
    KeychainFingerprintExists,
    KeychainFingerprintNotFound,
    KeychainKeyDataMismatch,
    KeychainLabelExists,
    KeychainLabelInvalid,
    KeychainSecretsMissing,
)
from chia.util.keychain import (
    Keychain,
    KeyData,
    KeyDataSecrets,
    bytes_from_mnemonic,
    bytes_to_mnemonic,
    generate_mnemonic,
    mnemonic_from_short_words,
    mnemonic_to_seed,
)


@dataclass
class KeyInfo:
    mnemonic: str
    entropy: bytes
    private_key: PrivateKey
    fingerprint: uint32
    public_key: G1Element
    bech32: str


_24keyinfo = KeyInfo(
    mnemonic=(
        "rapid this oven common drive ribbon bulb urban uncover napkin kitten usage enforce uncle unveil scene "
        "apart wire mystery torch peanut august flee fantasy"
    ),
    entropy=bytes.fromhex("b1fc1a7717343572077f7aecb25ded77c4a3d93b9e040a5f8649f2aa1e1e5632"),
    private_key=PrivateKey.from_bytes(
        bytes.fromhex("6c6bb4cc3dae03b8d0b327dd6765834464a883f7ca7df134970842055efe8afc")
    ),
    fingerprint=uint32(1310648153),
    public_key=G1Element.from_bytes(
        bytes.fromhex(
            "b5acf3599bc5fa5da1c00f6cc3d5bcf1560def67778b7f50a8c373a83f78761505b6250ab776e38a292e26628009aec4"
        )
    ),
    bech32="bls12381kkk0xkvmcha9mgwqpakv84du79tqmmm8w79h759gcde6s0mcwc2std39p2mhdcu29yhzvc5qpxhvgmknyl7",
)
_12keyinfo = KeyInfo(
    mnemonic=("steak rely trumpet cake banner easy consider cream marriage harvest truly shrimp"),
    entropy=bytes.fromhex("d516afa61021248b8bd197884d2fa5e3"),
    private_key=PrivateKey.from_bytes(
        bytes.fromhex("3aaec6598281320c4918a2d6ebf4c2bacabad5f85a45569fc3ba5159e13f94bf")
    ),
    fingerprint=uint32(688295223),
    public_key=G1Element.from_bytes(
        bytes.fromhex(
            "a9e652cb551d5978a9ee4b7aa52a4e826078a54b08a3d903c38611cb8a804a9a29c926e4f8549314a079e04ecde10cc1"
        )
    ),
    bech32="bls12381148n99j64r4vh320wfda222jwsfs83f2tpz3ajq7rscguhz5qf2dznjfxunu9fyc55pu7qnkduyxvzqskawt",
)


class TestKeychain:
    @pytest.mark.parametrize("key_info", [_24keyinfo, _12keyinfo])
    def test_basic_add_delete(
        self, key_info: KeyInfo, empty_temp_file_keyring: TempKeyring, seeded_random: random.Random
    ):
        kc: Keychain = Keychain(user="testing-1.8.0", service="chia-testing-1.8.0")
        kc.delete_all_keys()

        assert kc._get_free_private_key_index() == 0
        assert len(kc.get_all_private_keys()) == 0
        assert kc.get_first_private_key() is None
        assert kc.get_first_public_key() is None

        mnemonic = key_info.mnemonic
        entropy = bytes_from_mnemonic(mnemonic)
        assert bytes_to_mnemonic(entropy) == mnemonic
        mnemonic_2 = generate_mnemonic()
        fingerprint_2 = AugSchemeMPL.key_gen(mnemonic_to_seed(mnemonic_2)).get_g1().get_fingerprint()

        # misspelled words in the mnemonic
        bad_mnemonic = mnemonic.split(" ")
        bad_mnemonic[6] = "ZZZZZZ"
        with pytest.raises(ValueError, match="'ZZZZZZ' is not in the mnemonic dictionary; may be misspelled"):
            bytes_from_mnemonic(" ".join(bad_mnemonic))

        kc.add_key(mnemonic)
        assert kc._get_free_private_key_index() == 1
        assert len(kc.get_all_private_keys()) == 1

        kc.add_key(mnemonic_2)
        with pytest.raises(KeychainFingerprintExists) as e:
            kc.add_key(mnemonic_2)
        assert e.value.fingerprint == fingerprint_2
        assert kc._get_free_private_key_index() == 2
        assert len(kc.get_all_private_keys()) == 2

        assert kc._get_free_private_key_index() == 2
        assert len(kc.get_all_private_keys()) == 2
        assert len(kc.get_all_public_keys()) == 2
        assert kc.get_all_private_keys()[0] == kc.get_first_private_key()
        assert kc.get_all_public_keys()[0] == kc.get_first_public_key()

        assert len(kc.get_all_private_keys()) == 2

        seed_2 = mnemonic_to_seed(mnemonic)
        seed_key_2 = AugSchemeMPL.key_gen(seed_2)
        kc.delete_key_by_fingerprint(seed_key_2.get_g1().get_fingerprint())
        assert kc._get_free_private_key_index() == 0
        assert len(kc.get_all_private_keys()) == 1

        kc.delete_all_keys()
        assert kc._get_free_private_key_index() == 0
        assert len(kc.get_all_private_keys()) == 0

        kc.add_key(key_info.bech32, label=None, private=False)
        all_pks = kc.get_all_public_keys()
        assert len(all_pks) == 1
        assert all_pks[0] == key_info.public_key
        kc.delete_all_keys()

        kc.add_key(bytes_to_mnemonic(bytes32.random(seeded_random)))
        kc.add_key(bytes_to_mnemonic(bytes32.random(seeded_random)))
        kc.add_key(bytes_to_mnemonic(bytes32.random(seeded_random)))

        assert len(kc.get_all_public_keys()) == 3

        assert kc.get_first_private_key() is not None
        assert kc.get_first_public_key() is not None

        kc.delete_all_keys()
        kc.add_key(bytes_to_mnemonic(bytes32.random(seeded_random)))
        assert kc.get_first_public_key() is not None

    def test_add_private_key_label(self, empty_temp_file_keyring: TempKeyring):
        keychain: Keychain = Keychain(user="testing-1.8.0", service="chia-testing-1.8.0")

        key_data_0 = KeyData.generate(label="key_0")
        key_data_1 = KeyData.generate(label="key_1")
        key_data_2 = KeyData.generate(label=None)

        keychain.add_key(mnemonic_or_pk=key_data_0.mnemonic_str(), label=key_data_0.label)
        assert key_data_0 == keychain.get_key(key_data_0.fingerprint, include_secrets=True)

        # Try to add a new key with an existing label should raise
        with pytest.raises(KeychainLabelExists) as e:
            keychain.add_key(mnemonic_or_pk=key_data_1.mnemonic_str(), label=key_data_0.label)
        assert e.value.fingerprint == key_data_0.fingerprint
        assert e.value.label == key_data_0.label

        # Adding the same key with a valid label should work fine
        keychain.add_key(mnemonic_or_pk=key_data_1.mnemonic_str(), label=key_data_1.label)
        assert key_data_1 == keychain.get_key(key_data_1.fingerprint, include_secrets=True)

        # Trying to add an existing key should not have an impact on the existing label
        with pytest.raises(KeychainFingerprintExists):
            keychain.add_key(mnemonic_or_pk=key_data_0.mnemonic_str(), label="other label")
        assert key_data_0 == keychain.get_key(key_data_0.fingerprint, include_secrets=True)

        # Adding a key with no label should not assign any label
        keychain.add_key(mnemonic_or_pk=key_data_2.mnemonic_str(), label=key_data_2.label)
        assert key_data_2 == keychain.get_key(key_data_2.fingerprint, include_secrets=True)

        # All added keys should still be valid with their label
        assert all(
            # This must be compared to a tuple because the `.mnemonic` property is a list which makes the
            # class unhashable. We should eventually add support in streamable for varadic tuples and maybe remove
            # support for the mutable `list`.
            key_data in (key_data_0, key_data_1, key_data_2)  # noqa: PLR6201
            for key_data in keychain.get_keys(include_secrets=True)
        )

    def test_bip39_eip2333_test_vector(self, empty_temp_file_keyring: TempKeyring):
        kc: Keychain = Keychain(user="testing-1.8.0", service="chia-testing-1.8.0")
        kc.delete_all_keys()

        mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
        print("entropy to seed:", mnemonic_to_seed(mnemonic).hex())
        master_sk = kc.add_key(mnemonic)
        tv_master_int = 8075452428075949470768183878078858156044736575259233735633523546099624838313
        tv_child_int = 18507161868329770878190303689452715596635858303241878571348190917018711023613
        assert master_sk == PrivateKey.from_bytes(tv_master_int.to_bytes(32, "big"))
        child_sk = AugSchemeMPL.derive_child_sk(master_sk, 0)
        assert child_sk == PrivateKey.from_bytes(tv_child_int.to_bytes(32, "big"))

    def test_bip39_test_vectors(self):
        test_vectors_path = importlib_resources.files(chia._tests.util.__name__).joinpath("bip39_test_vectors.json")
        all_vectors = json.loads(test_vectors_path.read_text(encoding="utf-8"))

        for vector_list in all_vectors["english"]:
            entropy_bytes = bytes.fromhex(vector_list[0])
            mnemonic = vector_list[1]
            seed = bytes.fromhex(vector_list[2])

            assert bytes_from_mnemonic(mnemonic) == entropy_bytes
            assert bytes_to_mnemonic(entropy_bytes) == mnemonic
            assert mnemonic_to_seed(mnemonic) == seed

    def test_bip39_test_vectors_short(self):
        """
        Tests that the first 4 letters of each mnemonic phrase matches as if it were the full phrase
        """
        test_vectors_path = importlib_resources.files(chia._tests.util.__name__).joinpath("bip39_test_vectors.json")
        all_vectors = json.loads(test_vectors_path.read_text(encoding="utf-8"))

        for idx, [entropy_hex, full_mnemonic, seed, short_mnemonic] in enumerate(all_vectors["english"]):
            entropy_bytes = bytes.fromhex(entropy_hex)
            seed = bytes.fromhex(seed)

            assert mnemonic_from_short_words(short_mnemonic) == full_mnemonic
            assert bytes_from_mnemonic(short_mnemonic) == entropy_bytes
            assert bytes_to_mnemonic(entropy_bytes) == full_mnemonic
            assert mnemonic_to_seed(short_mnemonic) == seed

    def test_utf8_nfkd(self):
        # Test code from trezor:
        # Copyright (c) 2013 Pavol Rusnak
        # Copyright (c) 2017 mruddy
        # https://github.com/trezor/python-mnemonic/blob/master/tests/test_mnemonic.py
        # The same sentence in various UTF-8 forms
        words_nfkd = "Pr\u030ci\u0301s\u030cerne\u030c z\u030clut\u030couc\u030cky\u0301 ku\u030an\u030c u\u0301pe\u030cl d\u030ca\u0301belske\u0301 o\u0301dy za\u0301ker\u030cny\u0301 uc\u030cen\u030c be\u030cz\u030ci\u0301 pode\u0301l zo\u0301ny u\u0301lu\u030a"  # noqa: E501
        words_nfc = "P\u0159\xed\u0161ern\u011b \u017elu\u0165ou\u010dk\xfd k\u016f\u0148 \xfap\u011bl \u010f\xe1belsk\xe9 \xf3dy z\xe1ke\u0159n\xfd u\u010de\u0148 b\u011b\u017e\xed pod\xe9l z\xf3ny \xfal\u016f"  # noqa: E501
        words_nfkc = "P\u0159\xed\u0161ern\u011b \u017elu\u0165ou\u010dk\xfd k\u016f\u0148 \xfap\u011bl \u010f\xe1belsk\xe9 \xf3dy z\xe1ke\u0159n\xfd u\u010de\u0148 b\u011b\u017e\xed pod\xe9l z\xf3ny \xfal\u016f"  # noqa: E501
        words_nfd = "Pr\u030ci\u0301s\u030cerne\u030c z\u030clut\u030couc\u030cky\u0301 ku\u030an\u030c u\u0301pe\u030cl d\u030ca\u0301belske\u0301 o\u0301dy za\u0301ker\u030cny\u0301 uc\u030cen\u030c be\u030cz\u030ci\u0301 pode\u0301l zo\u0301ny u\u0301lu\u030a"  # noqa: E501

        seed_nfkd = mnemonic_to_seed(words_nfkd)
        seed_nfc = mnemonic_to_seed(words_nfc)
        seed_nfkc = mnemonic_to_seed(words_nfkc)
        seed_nfd = mnemonic_to_seed(words_nfd)

        assert seed_nfkd == seed_nfc
        assert seed_nfkd == seed_nfkc
        assert seed_nfkd == seed_nfd


def test_key_data_secrets_generate() -> None:
    secrets = KeyDataSecrets.generate()
    assert secrets.private_key == AugSchemeMPL.key_gen(mnemonic_to_seed(secrets.mnemonic_str()))
    assert secrets.entropy == bytes_from_mnemonic(secrets.mnemonic_str())


@pytest.mark.parametrize(
    "get_item, from_method", [("mnemonic", KeyDataSecrets.from_mnemonic), ("entropy", KeyDataSecrets.from_entropy)]
)
@pytest.mark.parametrize("key_info", [_24keyinfo, _12keyinfo])
def test_key_data_secrets_creation(
    key_info: KeyInfo, get_item: str, from_method: Callable[..., KeyDataSecrets]
) -> None:
    secrets = from_method(getattr(key_info, get_item))
    assert secrets.mnemonic == key_info.mnemonic.split()
    assert secrets.mnemonic_str() == key_info.mnemonic
    assert secrets.entropy == key_info.entropy
    assert secrets.private_key == key_info.private_key


@pytest.mark.parametrize("label", [None, "key"])
def test_key_data_generate(label: Optional[str]) -> None:
    key_data = KeyData.generate(label)
    assert key_data.private_key == AugSchemeMPL.key_gen(mnemonic_to_seed(key_data.mnemonic_str()))
    assert key_data.entropy == bytes_from_mnemonic(key_data.mnemonic_str())
    assert key_data.public_key == key_data.private_key.get_g1()
    assert key_data.fingerprint == key_data.private_key.get_g1().get_fingerprint()
    assert key_data.label == label


@pytest.mark.parametrize("label", [None, "key"])
@pytest.mark.parametrize(
    "get_item, from_method", [("mnemonic", KeyData.from_mnemonic), ("entropy", KeyData.from_entropy)]
)
@pytest.mark.parametrize("key_info", [_24keyinfo, _12keyinfo])
def test_key_data_creation(label: str, key_info: KeyInfo, get_item: str, from_method: Callable[..., KeyData]) -> None:
    key_data = from_method(getattr(key_info, get_item), label)
    assert key_data.fingerprint == key_info.fingerprint
    assert key_data.public_key == key_info.public_key
    assert key_data.mnemonic == key_info.mnemonic.split()
    assert key_data.mnemonic_str() == key_info.mnemonic
    assert key_data.entropy == key_info.entropy
    assert key_data.private_key == key_info.private_key
    assert key_data.label == label


@pytest.mark.parametrize("key_info", [_24keyinfo, _12keyinfo])
def test_key_data_without_secrets(key_info: KeyInfo) -> None:
    key_data = KeyData(key_info.fingerprint, key_info.public_key, None, None)
    assert key_data.secrets is None

    with pytest.raises(KeychainSecretsMissing):
        print(key_data.mnemonic)

    with pytest.raises(KeychainSecretsMissing):
        print(key_data.mnemonic_str())

    with pytest.raises(KeychainSecretsMissing):
        print(key_data.entropy)

    with pytest.raises(KeychainSecretsMissing):
        print(key_data.private_key)


@pytest.mark.parametrize(
    "input_data, data_type",
    [
        ((_24keyinfo.mnemonic.split()[:-1], _24keyinfo.entropy, _24keyinfo.private_key), "mnemonic"),
        ((_24keyinfo.mnemonic.split(), KeyDataSecrets.generate().entropy, _24keyinfo.private_key), "entropy"),
        ((_24keyinfo.mnemonic.split(), _24keyinfo.entropy, KeyDataSecrets.generate().private_key), "private_key"),
    ],
)
def test_key_data_secrets_post_init(input_data: tuple[list[str], bytes, PrivateKey], data_type: str) -> None:
    with pytest.raises(KeychainKeyDataMismatch, match=data_type):
        KeyDataSecrets(*input_data)


@pytest.mark.parametrize(
    "input_data, data_type",
    [
        (
            (
                _24keyinfo.fingerprint,
                G1Element(),
                None,
                KeyDataSecrets(_24keyinfo.mnemonic.split(), _24keyinfo.entropy, _24keyinfo.private_key),
            ),
            "public_key",
        ),
        ((_24keyinfo.fingerprint, G1Element(), None, None), "fingerprint"),
    ],
)
def test_key_data_post_init(
    input_data: tuple[uint32, G1Element, Optional[str], Optional[KeyDataSecrets]], data_type: str
) -> None:
    with pytest.raises(KeychainKeyDataMismatch, match=data_type):
        KeyData(*input_data)


@pytest.mark.parametrize("include_secrets", [True, False])
@pytest.mark.anyio
async def test_get_key(include_secrets: bool, get_temp_keyring: Keychain):
    keychain: Keychain = get_temp_keyring
    expected_keys = []
    # Add 10 keys and validate the result `get_key` for each of them after each addition
    for _ in range(10):
        key_data = KeyData.generate()
        mnemonic_str = key_data.mnemonic_str()
        if not include_secrets:
            key_data = replace(key_data, secrets=None)
        expected_keys.append(key_data)
        # The last created key should not yet succeed in `get_key`
        with pytest.raises(KeychainFingerprintNotFound):
            keychain.get_key(expected_keys[-1].fingerprint, include_secrets)
        # Add it and validate all keys
        keychain.add_key(mnemonic_str)
        assert all(keychain.get_key(key_data.fingerprint, include_secrets) == key_data for key_data in expected_keys)
    # Remove 10 keys and validate the result `get_key` for each of them after each removal
    while len(expected_keys) > 0:
        delete_key = expected_keys.pop()
        keychain.delete_key_by_fingerprint(delete_key.fingerprint)
        # The removed key should no longer succeed in `get_key`
        with pytest.raises(KeychainFingerprintNotFound):
            keychain.get_key(delete_key.fingerprint, include_secrets)
        assert all(keychain.get_key(key_data.fingerprint, include_secrets) == key_data for key_data in expected_keys)


@pytest.mark.parametrize("include_secrets", [True, False])
@pytest.mark.anyio
async def test_get_keys(include_secrets: bool, get_temp_keyring: Keychain):
    keychain: Keychain = get_temp_keyring
    # Should be empty on start
    assert keychain.get_keys(include_secrets) == []
    expected_keys = []
    # Add 10 keys and validate the result of `get_keys` after each addition
    for _ in range(10):
        key_data = KeyData.generate()
        mnemonic_str = key_data.mnemonic_str()
        if not include_secrets:
            key_data = replace(key_data, secrets=None)
        expected_keys.append(key_data)
        keychain.add_key(mnemonic_str)
        assert keychain.get_keys(include_secrets) == expected_keys
    # Remove all 10 keys and validate the result of `get_keys` after each removal
    while len(expected_keys) > 0:
        delete_key = expected_keys.pop()
        keychain.delete_key_by_fingerprint(delete_key.fingerprint)
        assert keychain.get_keys(include_secrets) == expected_keys
    # Should be empty again
    assert keychain.get_keys(include_secrets) == []


@pytest.mark.anyio
async def test_set_label(get_temp_keyring: Keychain) -> None:
    keychain: Keychain = get_temp_keyring
    # Generate a key and add it without label
    key_data_0 = KeyData.generate(label=None)
    keychain.add_key(mnemonic_or_pk=key_data_0.mnemonic_str(), label=None)
    assert key_data_0 == keychain.get_key(key_data_0.fingerprint, include_secrets=True)
    # Set a label and validate it
    key_data_0 = replace(key_data_0, label="key_0")
    assert key_data_0.label is not None
    keychain.set_label(fingerprint=key_data_0.fingerprint, label=key_data_0.label)
    assert key_data_0 == keychain.get_key(fingerprint=key_data_0.fingerprint, include_secrets=True)
    # Try to add the same label for a fingerprint where don't have a key for
    with pytest.raises(KeychainFingerprintNotFound):
        keychain.set_label(fingerprint=123456, label=key_data_0.label)
    # Add a second key
    key_data_1 = KeyData.generate(label="key_1")
    assert key_data_1.label is not None
    keychain.add_key(key_data_1.mnemonic_str())
    # Try to set the already existing label for the second key
    with pytest.raises(KeychainLabelExists) as e:
        keychain.set_label(fingerprint=key_data_1.fingerprint, label=key_data_0.label)
    assert e.value.fingerprint == key_data_0.fingerprint
    assert e.value.label == key_data_0.label

    # Set a different label to the second key and validate it
    keychain.set_label(fingerprint=key_data_1.fingerprint, label=key_data_1.label)
    assert key_data_0 == keychain.get_key(fingerprint=key_data_0.fingerprint, include_secrets=True)
    # All added keys should still be valid with their label

    # This must be compared to a tuple because the `.mnemonic` property is a list which makes the
    # class unhashable. We should eventually add support in streamable for varadic tuples and maybe remove
    # support for the mutable `list`.
    assert all(key_data in (key_data_0, key_data_1) for key_data in keychain.get_keys(include_secrets=True))  # noqa: PLR6201


@pytest.mark.parametrize(
    "label, message",
    [
        ("", "label can't be empty or whitespace only"),
        ("   ", "label can't be empty or whitespace only"),
        ("a\nb", "label can't contain newline or tab"),
        ("a\tb", "label can't contain newline or tab"),
        ("a" * 66, "label exceeds max length: 66/65"),
        ("a" * 70, "label exceeds max length: 70/65"),
    ],
)
@pytest.mark.anyio
async def test_set_label_invalid_labels(label: str, message: str, get_temp_keyring: Keychain) -> None:
    keychain: Keychain = get_temp_keyring
    key_data = KeyData.generate()
    keychain.add_key(key_data.mnemonic_str())
    with pytest.raises(KeychainLabelInvalid, match=message) as e:
        keychain.set_label(key_data.fingerprint, label)
    assert e.value.label == label


@pytest.mark.anyio
async def test_delete_label(get_temp_keyring: Keychain) -> None:
    keychain: Keychain = get_temp_keyring
    # Generate two keys and add them to the keychain
    key_data_0 = KeyData.generate(label="key_0")
    key_data_1 = KeyData.generate(label="key_1")

    def assert_delete_raises():
        # Try to delete the labels should fail now since they are gone already
        for key_data in [key_data_0, key_data_1]:
            with pytest.raises(KeychainFingerprintNotFound) as e:
                keychain.delete_label(key_data.fingerprint)
            assert e.value.fingerprint == key_data.fingerprint

    # Should pass here since the keys are not added yet
    assert_delete_raises()

    for key in [key_data_0, key_data_1]:
        keychain.add_key(mnemonic_or_pk=key.mnemonic_str(), label=key.label)
        assert key == keychain.get_key(key.fingerprint, include_secrets=True)
    # Delete the label of the first key, validate it was removed and make sure the other key retains its label
    keychain.delete_label(key_data_0.fingerprint)
    assert replace(key_data_0, label=None) == keychain.get_key(key_data_0.fingerprint, include_secrets=True)
    assert key_data_1 == keychain.get_key(key_data_1.fingerprint, include_secrets=True)
    # Re-add the label of the first key
    assert key_data_0.label is not None
    keychain.set_label(key_data_0.fingerprint, key_data_0.label)
    # Delete the label of the second key
    keychain.delete_label(key_data_1.fingerprint)
    assert key_data_0 == keychain.get_key(key_data_0.fingerprint, include_secrets=True)
    assert replace(key_data_1, label=None) == keychain.get_key(key_data_1.fingerprint, include_secrets=True)
    # Delete the label of the first key again, now both should have no label
    keychain.delete_label(key_data_0.fingerprint)
    assert replace(key_data_0, label=None) == keychain.get_key(key_data_0.fingerprint, include_secrets=True)
    assert replace(key_data_1, label=None) == keychain.get_key(key_data_1.fingerprint, include_secrets=True)
    # Should pass here since the key labels are both removed here
    assert_delete_raises()


@pytest.mark.parametrize("delete_all", [True, False])
@pytest.mark.anyio
async def test_delete_drops_labels(get_temp_keyring: Keychain, delete_all: bool) -> None:
    keychain: Keychain = get_temp_keyring
    # Generate some keys and add them to the keychain
    labels = [f"key_{i}" for i in range(5)]
    keys = [KeyData.generate(label=label) for label in labels]
    for key_data in keys:
        keychain.add_key(mnemonic_or_pk=key_data.mnemonic_str(), label=key_data.label)
        assert key_data == keychain.get_key(key_data.fingerprint, include_secrets=True)
        assert key_data.label is not None
        assert keychain.keyring_wrapper.keyring.get_label(key_data.fingerprint) == key_data.label
    if delete_all:
        # Delete the keys via `delete_all` and make sure no labels are left
        keychain.delete_all_keys()
        for key_data in keys:
            assert keychain.keyring_wrapper.keyring.get_label(key_data.fingerprint) is None
    else:
        # Delete the keys via fingerprint and make sure the label gets dropped
        for key_data in keys:
            keychain.delete_key_by_fingerprint(key_data.fingerprint)
            assert keychain.keyring_wrapper.keyring.get_label(key_data.fingerprint) is None
