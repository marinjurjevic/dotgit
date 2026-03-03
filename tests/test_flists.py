import os
import pytest
import socket

from dotgit.flists import Filelist

class TestFilelist:
    def write_flist(self, tmp_path, content):
        fname = os.path.join(tmp_path, 'filelist')
        with open(fname, 'w') as f:
            f.write(content)
        return fname

    def test_comments_and_empty(self, tmp_path):
        fname = self.write_flist(tmp_path, '# test comment\n    '+
                '\n  # spaced comment\n')

        flist = Filelist(fname)
        assert flist.groups == {}
        assert flist.files == {}

    def test_group(self, tmp_path):
        # Test where group name != hostname
        fname = self.write_flist(tmp_path, 'group=cat1,cat2,cat3')

        flist = Filelist(fname)
        assert flist.groups == {'group': ['cat1', 'cat2', 'cat3']}
        assert flist.files == {}

        # Test where group name == hostname
        fname = self.write_flist(tmp_path, socket.gethostname() + '=cat1,cat2,cat3')

        flist = Filelist(fname)
        assert flist.groups == {socket.gethostname(): ['cat1', 'cat2', 'cat3', socket.gethostname()]}
        assert flist.files == {}

    def test_common_file(self, tmp_path):
        fname = self.write_flist(tmp_path, 'common_file/with/path')

        flist = Filelist(fname)
        assert flist.groups == {}
        assert flist.files == {'common_file/with/path': [{
            'categories': ['common'],
            'plugin': 'plain'
        }]}

    def test_file(self, tmp_path):
        fname = self.write_flist(tmp_path, 'file:cat1,cat2\nfile:cat3\n')

        flist = Filelist(fname)
        assert flist.groups == {}
        assert flist.files == {
            'file': [{
                'categories': ['cat1', 'cat2'],
                'plugin': 'plain'
            }, {
                'categories': ['cat3'],
                'plugin': 'plain'
            }]}

    def test_mix(self, tmp_path):
        fname = self.write_flist(tmp_path,
                'group=cat1,cat2\ncfile\n#comment\nnfile:cat1,cat2\n')

        flist = Filelist(fname)
        assert flist.groups == {'group': ['cat1', 'cat2']}
        assert flist.files == {
            'cfile': [{
                'categories': ['common'],
                'plugin': 'plain'
            }],
            'nfile': [{
                'categories': ['cat1', 'cat2'],
                'plugin': 'plain'
            }]}

    def test_cat_plugin(self, tmp_path):
        fname = self.write_flist(tmp_path, 'file:cat1,cat2|encrypt')

        flist = Filelist(fname)
        assert flist.files == {
            'file': [{
                'categories': ['cat1', 'cat2'],
                'plugin': 'encrypt'
            }]}

    def test_nocat_plugin(self, tmp_path):
        fname = self.write_flist(tmp_path, 'file|encrypt')

        flist = Filelist(fname)
        assert flist.files == {
            'file': [{
                'categories': ['common'],
                'plugin': 'encrypt'
            }]}

    def test_activate_groups(self, tmp_path):
        fname = self.write_flist(tmp_path, 'group=cat1,cat2\nfile:cat1')

        flist = Filelist(fname)
        assert flist.activate(['group']) == {
            'file': {
                'categories': ['cat1'],
                'plugin': 'plain'
            }}

    def test_activate_normal(self, tmp_path):
        fname = self.write_flist(tmp_path, 'file:cat1,cat2\nfile2:cat3\n')

        flist = Filelist(fname)
        assert flist.activate(['cat2']) == {
            'file': {
                'categories': ['cat1', 'cat2'],
                'plugin': 'plain',
            }}

    def test_activate_duplicate(self, tmp_path):
        fname = self.write_flist(tmp_path, 'file:cat1,cat2\nfile:cat2\n')

        flist = Filelist(fname)
        with pytest.raises(RuntimeError):
            flist.activate(['cat2'])

    def test_arbitration_group_later_wins(self, tmp_path):
        """Later category in group takes precedence over earlier."""
        # group defines order: common(0), alias(1), zsh(2), vim(3)
        fname = self.write_flist(tmp_path,
                                 'myhost=common,alias,zsh,vim\n'
                                 '.vimrc\n'          # common (index 0)
                                 '.vimrc:vim\n')     # vim (index 3)

        flist = Filelist(fname)
        # simulates `dotgit restore` on myhost: ['common', 'myhost']
        # expands to ['common', 'common', 'alias', 'zsh', 'vim', 'myhost']
        # vim (index 4) > common (index 1), so vim version wins
        result = flist.activate(['common', 'myhost'])
        assert result == {
            '.vimrc': {
                'categories': ['vim'],
                'plugin': 'plain',
            }}

    def test_arbitration_group_common_fallback(self, tmp_path):
        """On a different host, only common matches as fallback."""
        fname = self.write_flist(tmp_path,
                                 'myhost=common,alias,zsh,vim\n'
                                 '.profile\n'           # common
                                 '.profile:vim\n')      # vim — only in myhost group

        flist = Filelist(fname)
        # on 'otherhost' (no group defined), categories stay ['common', 'otherhost']
        # 'vim' is not in the active set, so only common matches
        result = flist.activate(['common', 'otherhost'])
        assert result == {
            '.profile': {
                'categories': ['common'],
                'plugin': 'plain',
            }}

    def test_arbitration_group_order_matters(self, tmp_path):
        """Position inside group determines which category wins the file."""
        # alias is before zsh in the group, so zsh has higher priority
        fname = self.write_flist(tmp_path,
                                 'myhost=alias,zsh\n'
                                 '.config:alias\n'
                                 '.config:zsh\n')

        flist = Filelist(fname)
        result = flist.activate(['common', 'myhost'])
        # flattened: ['common', 'alias', 'zsh', 'myhost']
        # zsh (index 2) > alias (index 1) → zsh wins
        assert result == {
            '.config': {
                'categories': ['zsh'],
                'plugin': 'plain',
            }}

    def test_arbitration_group_filelist_entry_order_irrelevant(self, tmp_path):
        """Order of entries in filelist doesn't matter; group order does."""
        # specific entry listed BEFORE common entry in filelist
        fname = self.write_flist(tmp_path,
                                 'myhost=common,zsh\n'
                                 '.zshrc:zsh\n'
                                 '.zshrc\n')

        flist = Filelist(fname)
        result = flist.activate(['common', 'myhost'])
        # flattened: ['common', 'common', 'zsh', 'myhost']
        # zsh (index 2) > common (index 1) → zsh wins regardless of filelist order
        assert result == {
            '.zshrc': {
                'categories': ['zsh'],
                'plugin': 'plain',
            }}

    def test_arbitration_group_with_plugin(self, tmp_path):
        """Arbitration works correctly with non-default plugins."""
        fname = self.write_flist(tmp_path,
                                 'myhost=common,ssh\n'
                                 '.ssh/config|encrypt\n'
                                 '.ssh/config:ssh|encrypt\n')

        flist = Filelist(fname)
        result = flist.activate(['common', 'myhost'])
        assert result == {
            '.ssh/config': {
                'categories': ['ssh'],
                'plugin': 'encrypt',
            }}

    def test_arbitration_group_no_match(self, tmp_path):
        """File with category not in any active group is excluded."""
        fname = self.write_flist(tmp_path,
                                 'myhost=alias,zsh\n'
                                 '.profile:vim\n')

        flist = Filelist(fname)
        # vim is not in the myhost group, and not in ['common', 'myhost']
        result = flist.activate(['common', 'myhost'])
        assert result == {}

    def test_arbitration_group_equal_priority_raises(self, tmp_path):
        """Two entries matching the same highest-priority category is an error."""
        fname = self.write_flist(tmp_path,
                                 'myhost=alias,zsh\n'
                                 'file:alias,zsh\n'    # matches zsh (highest)
                                 'file:zsh\n')         # also matches zsh

        flist = Filelist(fname)
        # both entries have max priority from 'zsh' → ambiguous
        with pytest.raises(RuntimeError):
            flist.activate(['common', 'myhost'])

    def test_manifest(self, tmp_path):
        fname = self.write_flist(tmp_path,
                                 'group=cat1,cat2\ncfile\nnfile:cat1,cat2\n'
                                 'gfile:group\npfile:cat1,cat2|encrypt')

        flist = Filelist(fname)
        manifest = flist.manifest()

        assert type(manifest) is dict
        assert sorted(manifest) == sorted(['plain', 'encrypt'])

        assert sorted(manifest['plain']) == sorted(['common/cfile',
                                                    'cat1/nfile', 'cat2/nfile',
                                                    'cat1/gfile',
                                                    'cat2/gfile'])

        assert sorted(manifest['encrypt']) == sorted(['cat1/pfile',
                                                      'cat2/pfile'])
