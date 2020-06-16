import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import matplotlib.gridspec as gridspec

import astropy.units as U
import astropy.constants as C

import h5py
import time
import numpy as np
import pandas as pds
import astropy.wcs as awc
import subprocess as subpro
import astropy.io.fits as fits

from scipy import ndimage
from astropy import cosmology as apcy
from light_measure import light_measure, light_measure_rn

from mpi4py import MPI
commd = MPI.COMM_WORLD
rank = commd.Get_rank()
cpus = commd.Get_size()

kpc2cm = U.kpc.to(U.cm)
Mpc2pc = U.Mpc.to(U.pc)
Mpc2cm = U.Mpc.to(U.cm)
kpc2m = U.kpc.to(U.m)
rad2asec = U.rad.to(U.arcsec)
pc2cm = U.pc.to(U.cm)
Msun2kg = U.M_sun.to(U.kg)
Lsun = C.L_sun.value*10**7
G = C.G.value

# cosmology model
Test_model = apcy.Planck15.clone(H0 = 67.74, Om0 = 0.311)
H0 = Test_model.H0.value
h = H0/100
Omega_m = Test_model.Om0
Omega_lambda = 1.-Omega_m
Omega_k = 1.- (Omega_lambda + Omega_m)

pixel, z_ref = 0.396, 0.250
Da_ref = Test_model.angular_diameter_distance(z_ref).value
Jy = 10**(-23) # (erg/s)/cm^2
f0 = 3631 * Jy # (erg/s)/cm^-2
R0 = 1 # Mpc
Angu_ref = (R0/Da_ref)*rad2asec
Rpp = Angu_ref/pixel

load = '/mnt/ddnfs/data_users/cxkttwl/ICL/data/'
tmp = '/mnt/ddnfs/data_users/cxkttwl/PC/'
band = ['r', 'g', 'i', 'u', 'z']
mag_add = np.array([0, 0, 0, -0.04, 0.02])

def img_stack(band_id, sub_z, sub_ra, sub_dec):
	stack_N = len(sub_z)
	kk = np.int(band_id)
	x0, y0 = 2427, 1765
	Nx = np.linspace(0, 4854, 4855)
	Ny = np.linspace(0, 3530, 3531)

	sum_array = np.zeros((len(Ny), len(Nx)), dtype = np.float)
	count_array = np.ones((len(Ny), len(Nx)), dtype = np.float) * np.nan
	p_count = np.zeros((len(Ny), len(Nx)), dtype = np.float)

	id_nx = 0.
	for jj in range(stack_N):
		ra_g = sub_ra[jj]
		dec_g = sub_dec[jj]
		z_g = sub_z[jj]

		data = fits.open(load + 
			'mock_ccd/mock_resamp/mock_resam-%s-ra%.3f-dec%.3f-redshift%.3f.fits' % (band[kk], ra_g, dec_g, z_g))
		img = data[0].data
		xn = data[0].header['CENTER_X']
		yn = data[0].header['CENTER_Y']
		la0 = np.int(y0 - yn)
		la1 = np.int(y0 - yn + img.shape[0])
		lb0 = np.int(x0 - xn)
		lb1 = np.int(x0 - xn + img.shape[1])

		idx = np.isnan(img)
		idv = np.where(idx == False)
		sum_array[la0:la1, lb0:lb1][idv] = sum_array[la0:la1, lb0:lb1][idv] + img[idv]
		count_array[la0: la1, lb0: lb1][idv] = img[idv]
		id_nan = np.isnan(count_array)
		id_fals = np.where(id_nan == False)
		p_count[id_fals] += 1.
		count_array[la0: la1, lb0: lb1][idv] = np.nan

		id_nx += 1.
	p_count[0, 0] = id_nx # record the number of stack image
	with h5py.File(tmp + 'mock_sum_%d_in_%s_band.h5' % (rank, band[kk]), 'w') as f:
		f['a'] = np.array(sum_array)
	with h5py.File(tmp + 'mock_pcount_%d_in_%s_band.h5' % (rank, band[kk]), 'w') as f:
		f['a'] = np.array(p_count)

	return

def cov_MX(radius, pros):
	flux_array = np.array(pros)
	r_array = np.array(radius)
	Nt = len(flux_array)
	SB_value = []
	R_value = []
	for ll in range(Nt):
		id_nan = np.isnan(flux_array[ll])
		setx = flux_array[ll][id_nan == False]
		setr = r_array[ll][id_nan == False]
		SB_value.append(setx)
		R_value.append(setr)
	SB_value = np.array(SB_value)
	R_value = np.array(R_value)
	R_mean_img = np.nanmean(R_value, axis = 0)
	cov_Mx_img = np.corrcoef(SB_value.T)
	return R_mean_img, cov_Mx_img

def betwn_SB(data, R_low, R_up, cx, cy, pix_size, z0, band_id):

	betwn_r, betwn_Intns, betwn_err = light_measure_rn(data, R_low, R_up, cx, cy, pix_size, z0)
	betwn_lit = 22.5 - 2.5 * np.log10(betwn_Intns) + 2.5 * np.log10(pixel**2) + mag_add[band_id]
	flux0 = betwn_Intns + betwn_err
	flux1 = betwn_Intns - betwn_err
	dSB0 = 22.5 - 2.5 * np.log10(flux0) + 2.5 * np.log10(pixel**2) + mag_add[band_id]
	dSB1 = 22.5 - 2.5 * np.log10(flux1) + 2.5 * np.log10(pixel**2) + mag_add[band_id]
	btn_err0 = betwn_lit - dSB0
	btn_err1 = dSB1 - betwn_lit
	id_nan = np.isnan(dSB1)
	if id_nan == True:
		btn_err1 = 100.

	return betwn_r, betwn_lit, btn_err0, btn_err1, betwn_Intns, betwn_err

def SB_pro(img, R_bins, R_min, R_max, Cx, Cy, pix_size, zg, band_id):
	kk = band_id
	Intns, Intns_r, Intns_err = light_measure(img, R_bins, R_min, R_max, Cx, Cy, pix_size, zg)
	SB = 22.5 - 2.5 * np.log10(Intns) + 2.5 * np.log10(pixel**2) + mag_add[kk]
	flux0 = Intns + Intns_err
	flux1 = Intns - Intns_err
	dSB0 = 22.5 - 2.5 * np.log10(flux0) + 2.5 * np.log10(pixel**2) + mag_add[kk]
	dSB1 = 22.5 - 2.5 * np.log10(flux1) + 2.5 * np.log10(pixel**2) + mag_add[kk]
	err0 = SB - dSB0
	err1 = dSB1 - SB
	id_nan = np.isnan(SB)
	SB_out, R_out, out_err0, out_err1 = SB[id_nan == False], Intns_r[id_nan == False], err0[id_nan == False], err1[id_nan == False]
	dSB0, dSB1 = dSB0[id_nan == False], dSB1[id_nan == False]
	idx_nan = np.isnan(dSB1)
	out_err1[idx_nan] = 100.

	return R_out, SB_out, out_err0, out_err1, Intns, Intns_r, Intns_err
"""
#####################
### stacking image
with h5py.File(load + 'mpi_h5/sample_catalog.h5', 'r') as f:
	catalogue = np.array(f['a'])
z = catalogue[0]
ra = catalogue[1]
dec = catalogue[2]

N_tt = 3000
np.random.seed(2)
tt0 = np.random.choice(len(z), size = N_tt, replace = False)
set_z = z[tt0]
set_ra = ra[tt0]
set_dec = dec[tt0]

for tt in range(3):
	m, n = divmod(N_tt, cpus)
	N_sub0, N_sub1 = m * rank, (rank + 1) * m
	if rank == cpus - 1:
		N_sub1 += n
	img_stack(tt, set_z[N_sub0 :N_sub1], set_ra[N_sub0 :N_sub1], set_dec[N_sub0 :N_sub1])
commd.Barrier()

if rank == 0:
	for qq in range(3):

		for pp in range(cpus):

			with h5py.File(tmp + 'mock_sum_%d_in_%s_band.h5' % (pp, band[qq]), 'r')as f:
				sum_img = np.array(f['a'])
			with h5py.File(tmp + 'mock_pcount_%d_in_%s_band.h5' % (pp, band[qq]), 'r') as f:
				p_count = np.array(f['a'])

			sub_mean = sum_img / p_count
			id_zeros = sub_mean == 0.
			sub_mean[id_zeros] = np.nan
			id_inf = np.isinf(sub_mean)
			sub_mean[id_inf] = np.nan

			with h5py.File( load + 'mock_ccd/correlation_test/%s_band_%d_sub-stack.h5' % (band[qq], pp), 'w') as f:
				f['a'] = np.array(sub_mean)

commd.Barrier()
#####################
"""
rich_a0, rich_a1, rich_a2 = 20, 30, 50
R_cut, bins_0, bins_1 = 1318, 80, 3 # around 2.1Mpc set
R_min_0, R_max_0 = 1, 1.6e3 # kpc
R_min_1, R_max_1 = 1.8e3, 2.1e3 # kpc
r_a0, r_a1 = 1.6e3, 1.8e3

x0, y0 = 2427, 1765
Nx = np.linspace(0, 4854, 4855)
Ny = np.linspace(0, 3530, 3531)

N_bin = 30
for kk in range(rank, rank + 1):

	stack_r = []
	stack_sb = []

	for nn in range(N_bin):

		with h5py.File( load + 'mock_ccd/correlation_test/%s_band_%d_sub-stack.h5' % (band[kk], nn), 'r') as f:
			sub_mean = np.array(f['a'])
		ss_img = sub_mean[y0 - R_cut: y0 + R_cut, x0 - R_cut: x0 + R_cut]

		Rt_0, SBt_0, t_err0_0, t_err1_0, Intns_0_0, Intns_r_0_0, Intns_err_0_0 = SB_pro(
			ss_img, bins_0, R_min_0, R_max_0, R_cut, R_cut, pixel, z_ref, kk)
		Rt_1, SBt_1, t_err0_1, t_err1_1, Intns_0_1, Intns_r_0_1, Intns_err_0_1 = SB_pro(
			ss_img, bins_1, R_min_1, R_max_1, R_cut, R_cut, pixel, z_ref, kk)
		betwn_r, betwn_lit, btn_err0, btn_err1, betwn_Intns, betwn_err = betwn_SB(ss_img, r_a0, r_a1, R_cut, R_cut, pixel, z_ref, kk)

		Rt = np.r_[Rt_0, betwn_r, Rt_1]
		SBt = np.r_[SBt_0, betwn_lit, SBt_1]
		t_err0 = np.r_[t_err0_0, btn_err0, t_err0_1]
		t_err1 = np.r_[t_err1_0, btn_err1, t_err1_1]
		Intns_0 = np.r_[Intns_0_0, betwn_Intns, Intns_0_1]
		Intns_r_0 = np.r_[Intns_r_0_0, betwn_r, Intns_r_0_1]
		Intns_err_0 = np.r_[Intns_err_0_0, betwn_err, Intns_err_0_1]

		Intns_0, Intns_err_0 = Intns_0 / pixel**2, Intns_err_0 / pixel**2
		stack_sb.append(Intns_0)
		stack_r.append(Intns_r_0)

		dmp_array = np.array([Intns_r_0, Intns_0, Intns_err_0])
		with h5py.File( load + 'mock_ccd/correlation_test/%s_band_%d_sub-stack_clust_SB.h5' % (band[kk], nn), 'w') as f:
			f['a'] = np.array(dmp_array)
		with h5py.File( load + 'mock_ccd/correlation_test/%s_band_%d_sub-stack_clust_SB.h5' % (band[kk], nn) ) as f:
			for ll in range(len(dmp_array)):
				f['a'][ll,:] = dmp_array[ll,:]
		"""
		with h5py.File( load + 'mock_ccd/correlation_test/%s_band_%d_sub-stack_clust_SB.h5' % (band[kk], nn), 'r') as f:
			dmp_array = np.array(f['a'])
		stack_sb.append(dmp_array[1])
		stack_r.append(dmp_array[0])
		"""
	R_mean_img, cov_Mx_img = cov_MX(stack_r, stack_sb)

	plt.figure()
	ax0 = plt.subplot(111)
	ax0.set_title('%s band mock img SB correlation matrix' % band[kk])

	tf = ax0.imshow(cov_Mx_img, cmap = 'seismic', origin = 'lower', vmin = -1, vmax = 1)
	plt.colorbar(tf, ax = ax0, fraction = 0.045, pad = 0.01)
	ax0.set_xlim(0, len(R_mean_img) - 1)
	ax0.set_ylim(0, len(R_mean_img) - 1)

	xtick = ax0.get_xticks(minor = False)
	idx = xtick < len(R_mean_img)
	ax0.set_xticks(xtick[idx])
	ax0.set_xticklabels('%.1f' % ll for ll in R_mean_img[ xtick[idx].astype(int) ])
	ax0.set_xlabel('R [kpc]')

	ytick = ax0.get_yticks(minor = False)
	idx = ytick < len(R_mean_img)
	ax0.set_yticks(ytick[idx])
	ax0.set_yticklabels('%.1f' % ll for ll in R_mean_img[ ytick[idx].astype(int) ])
	ax0.set_ylabel('R [kpc]')

	plt.subplots_adjust(left = 0.2, right = 0.8, bottom = 0.1, top = 0.9)
	plt.savefig( load + 'mock_ccd/correlation_test/%s_band_cov_MX.png' % (band[kk]), dpi = 300)
	plt.close()
