#!/usr/bin/perl
# Fixed, bounded read-only helpers for the PHP host probe. No shell or GPU ioctl.
use strict;
use warnings;
use JSON::PP;
use Errno qw(EBUSY);
use Fcntl qw(O_RDONLY);
use Socket qw(SOL_SOCKET SO_PEERCRED);

alarm 2;

sub small_value {
    my ($path, $numeric, $busy) = @_;
    sysopen(my $file, $path, O_RDONLY) or die "metric open failed\n";
    my $raw = '';
    my $length = sysread($file, $raw, 65);
    my $errno = 0 + $!;
    close($file) or die "metric close failed\n";
    return (undef, 'EBUSY') if !defined($length) && $busy && $errno == EBUSY;
    die "metric read failed\n" unless defined($length) && $length > 0 && $length <= 64;
    chomp($raw);
    die "metric format failed\n" if $numeric && $raw !~ /\A[0-9]{1,18}\z/;
    return ($numeric ? 0 + $raw : $raw, undef);
}

sub telemetry {
    my ($pci) = @_;
    die "PCI format failed\n" unless $pci =~ /\A[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]\z/;
    my $base = "/sys/bus/pci/devices/$pci";
    my ($before) = small_value("$base/power/runtime_status", 0, 0);
    my ($active) = small_value("$base/power/runtime_active_time", 1, 0);
    my ($busy, $errno) = small_value("$base/gpu_busy_percent", 1, 1);
    my ($used) = small_value("$base/mem_info_vram_used", 1, 0);
    my ($after) = small_value("$base/power/runtime_status", 0, 0);
    die "runtime transition\n" unless $before eq $after && $after =~ /\A(active|suspended)\z/;
    die "runtime not previously active\n" if $after eq 'suspended' && $active == 0;
    die "busy counter invalid\n" if defined($busy) && $busy > 100;
    die "unavailable active counter\n" if defined($errno) && $after ne 'suspended';
    return {runtime_status => $after, runtime_active_ms => $active,
        gpu_busy_percent => $busy, gpu_busy_errno => $errno, vram_used_bytes => $used};
}

sub peer {
    open(my $socket, '<&=3') or die "peer descriptor missing\n";
    my $raw = getsockopt($socket, SOL_SOCKET, SO_PEERCRED);
    die "peer credentials missing\n" unless defined($raw) && length($raw) == 12;
    my ($pid, $uid, $gid) = unpack('i3', $raw);
    die "peer credentials invalid\n" unless $pid > 1 && $uid >= 0 && $gid >= 0;
    return {pid => $pid, uid => $uid, gid => $gid};
}

my $mode = shift @ARGV // '';
my $result;
if ($mode eq 'telemetry' && @ARGV == 1) { $result = telemetry($ARGV[0]); }
elsif ($mode eq 'peer' && @ARGV == 0) { $result = peer(); }
else { die "fixed operation required\n"; }
print JSON::PP->new->canonical->encode($result), "\n";
