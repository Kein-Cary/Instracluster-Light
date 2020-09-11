import h5py
import numpy as np
import pandas as pds
import astropy.wcs as awc
import astropy.io.ascii as asc
import astropy.io.fits as fits

import scipy.stats as sts
import astropy.units as U
import astropy.constants as C
from groups import groups_find_func

def diffuse_identi_func(band, set_ra, set_dec, set_z, data_file, rule_out_file, remain_file,):
	"""
	band : observation band
	set_ra, set_dec, set_z : smaples need to find out-liers
	data_file : the observational imgs,(format: 'XXXX/XXX/XXX.XXX') and those imgs
				have been masked
	{out-put file : XXX.csv
	rule_out_file : the file name of out-put catalogue for exclude imgs (not include in stacking)
	remain_file : the file name of out-put catalogue for stacking imgs (stacking imgs) }
	"""
	bad_ra, bad_dec, bad_z, bad_bcgx, bad_bcgy = [], [], [], [], []
	norm_ra, norm_dec, norm_z, norm_bcgx, norm_bcgy = [], [], [], [], []

	for kk in range( len(set_z) ):

		ra_g, dec_g, z_g = set_ra[kk], set_dec[kk], set_z[kk]

		file = data_file % (band, ra_g, dec_g, z_g)
		data = fits.open( file )
		img = data[0].data
		head = data[0].header
		wcs_lis = awc.WCS(head)
		xn, yn = wcs_lis.all_world2pix(ra_g * U.deg, dec_g * U.deg, 1)
		remain_img = img.copy()

		ca0, ca1 = np.int(img.shape[0] / 2), np.int(img.shape[1] / 2)
		cen_D = 500
		flux_cen = remain_img[ca0 - cen_D: ca0 + cen_D, ca1 - cen_D: ca1 + cen_D]

		N_step = 200

		cen_lx = np.arange(0, 1100, N_step)
		cen_ly = np.arange(0, 1100, N_step)
		nl0, nl1 = len(cen_ly), len(cen_lx)

		sub_pock_pix = np.zeros((nl0 - 1, nl1 - 1), dtype = np.float)
		sub_pock_flux = np.zeros((nl0 - 1, nl1 - 1), dtype = np.float)
		for nn in range(nl0 - 1):
			for tt in range(nl1 - 1):
				sub_flux = flux_cen[ cen_ly[nn]: cen_ly[nn+1], cen_lx[tt]: cen_lx[tt+1] ]
				id_nn = np.isnan(sub_flux)
				sub_pock_flux[nn,tt] = np.nanmean(sub_flux)
				sub_pock_pix[nn,tt] = len(sub_flux[id_nn == False])

		## mu, sigma of center region
		id_Nzero = sub_pock_pix > 100
		mu = np.nanmean( sub_pock_flux[id_Nzero] )
		sigm = np.nanstd( sub_pock_flux[id_Nzero] )

		ly = np.arange(0, img.shape[0], N_step)
		ly = np.r_[ly, img.shape[0] - N_step, img.shape[0] ]
		lx = np.arange(0, img.shape[1], N_step)
		lx = np.r_[lx, img.shape[1] - N_step, img.shape[1] ]
		patch_mean = np.zeros( (len(ly) - 1, len(lx) - 1), dtype = np.float )
		patch_pix = np.zeros( (len(ly) - 1, len(lx) - 1), dtype = np.float )
		for nn in range( len(ly) - 1 ):
			for tt in range( len(lx) - 1 ):
				if nn == len(ly) - 3:
					nn += 1
				if tt == len(lx) - 3:
					tt += 1
				sub_flux = remain_img[ly[nn]: ly[nn + 1], lx[tt]: lx[tt+1]]
				id_nn = np.isnan(sub_flux)
				patch_mean[nn,tt] = np.mean( sub_flux[id_nn == False] )
				patch_pix[nn,tt] = len( sub_flux[id_nn == False] )

		id_zeros = patch_pix == 0.
		patch_pix[id_zeros] = np.nan
		patch_mean[id_zeros] = np.nan
		over_sb = (patch_mean - mu) / sigm

		over_sb = np.delete(over_sb, -2, axis = 0)
		over_sb = np.delete(over_sb, -2, axis = 1)
		lx = np.delete(lx, -3)
		lx = np.delete(lx, -1)
		ly = np.delete(ly, -3)
		ly = np.delete(ly, -1)

		##### img selection
		lim_sb = 5.5
		### first select
		identi = over_sb > lim_sb

		if np.sum(identi) < 1:
			norm_ra.append(ra_g)
			norm_dec.append(dec_g)
			norm_z.append(z_g)
			norm_bcgx.append(xn)
			norm_bcgy.append(yn)

		else:
			### lighter blocks find
			copy_arr = over_sb.copy()
			idnn = np.isnan(over_sb)
			copy_arr[idnn] = 100
			source_n, coord_x, coord_y = groups_find_func(copy_arr, lim_sb)

			lo_xs = lx[ [np.min( ll ) for ll in coord_x] ]
			hi_xs = lx[ [np.max( ll ) for ll in coord_x] ]
			lo_ys = ly[ [np.min( ll ) for ll in coord_y] ]
			hi_ys = ly[ [np.max( ll ) for ll in coord_y] ]
			### mainly focus on regions which close to edges
			idux = (lo_xs <= 500) | (2000 - hi_xs <= 500)
			iduy = (lo_ys <= 500) | (1400 - hi_ys <= 500)
			idu = idux | iduy

			### select groups with block number larger or equal to 3
			idv_s = (np.array(source_n) >= 3)
			id_pat_s = idu & idv_s

			if np.sum(id_pat_s) < 1:
				norm_ra.append(ra_g)
				norm_dec.append(dec_g)
				norm_z.append(z_g)
				norm_bcgx.append(xn)
				norm_bcgy.append(yn)

			else:
				id_True = np.where(id_pat_s == True)[0]
				loop_N = np.sum(id_pat_s)
				pur_N = np.zeros(loop_N, dtype = np.int)
				pur_mask = np.zeros(loop_N, dtype = np.int)
				pur_outlier = np.zeros(loop_N, dtype = np.int)

				for ll in range( loop_N ):
					id_group = id_True[ll]
					tot_pont = source_n[ id_group ]
					tmp_arr = copy_arr[ coord_y[ id_group ], coord_x[ id_group ] ]
					id_out = tmp_arr == 100.
					id_2_bright = tmp_arr > 9.5

					pur_N[ll] = tot_pont - np.sum(id_out)
					pur_mask[ll] = np.sum(id_out)

					pur_outlier[ll] = np.sum(id_2_bright) * ( np.sum(id_out) == 0)

				## at least 2 blocks have mean value above the lim_sb and close to a big mask region
				idnum = ( (pur_N >= 2) & (pur_mask >= 1) ) | (pur_outlier >= 1)

				if np.sum(idnum) >= 1:
					bad_ra.append(ra_g)
					bad_dec.append(dec_g)
					bad_z.append(z_g)
					bad_bcgx.append(xn)
					bad_bcgy.append(yn)

				else:
					## search for larger groups
					# each group include 5 patches at least
					idv = np.array(source_n) >= 5
					id_pat = idu & idv

					if np.sum(id_pat) < 1:
						norm_ra.append(ra_g)
						norm_dec.append(dec_g)
						norm_z.append(z_g)
						norm_bcgx.append(xn)
						norm_bcgy.append(yn)

					else:

						id_True = np.where(id_pat == True)[0]
						loop_N = np.sum(id_pat)
						pur_N = np.zeros(loop_N, dtype = np.int)
						for ll in range( loop_N ):
							id_group = id_True[ll]
							tot_pont = source_n[ id_group ]
							tmp_arr = copy_arr[ coord_y[ id_group ], coord_x[ id_group ] ]
							id_out = tmp_arr == 100.
							pur_N[ll] = tot_pont - np.sum(id_out)

						idnum = pur_N >= 2 ## at least 2 blocks have mean value above the lim_sb,(except mask region)

						if np.sum(idnum) < 1:
							norm_ra.append(ra_g)
							norm_dec.append(dec_g)
							norm_z.append(z_g)
							norm_bcgx.append(xn)
							norm_bcgy.append(yn)

						else:
							bad_ra.append(ra_g)
							bad_dec.append(dec_g)
							bad_z.append(z_g)
							bad_bcgx.append(xn)
							bad_bcgy.append(yn)
	### 'bad' imgs
	x_ra = np.array( bad_ra )
	x_dec = np.array( bad_dec )
	x_z = np.array( bad_z )
	x_xn = np.array( bad_bcgx )
	x_yn = np.array( bad_bcgy )
	keys = ['ra', 'dec', 'z', 'bcg_x', 'bcg_y']
	values = [x_ra, x_dec, x_z, x_xn, x_yn]
	fill = dict(zip(keys, values))
	data = pds.DataFrame(fill)
	data.to_csv(rule_out_file)
	### normal imgs
	x_ra = np.array( norm_ra )
	x_dec = np.array( norm_dec )
	x_z = np.array( norm_z )
	x_xn = np.array( norm_bcgx )
	x_yn = np.array( norm_bcgy )
	keys = ['ra', 'dec', 'z', 'bcg_x', 'bcg_y']
	values = [x_ra, x_dec, x_z, x_xn, x_yn]
	fill = dict(zip(keys, values))
	data = pds.DataFrame(fill)
	data.to_csv(remain_file)

	return

def main():

	import time

	band = ['r', 'g', 'i']
	home = '/media/xkchen/My Passport/data/SDSS/'

	##### cluster imgs
	dat = pds.read_csv('cluster_tot-r-band_norm-img_cat.csv')
	set_ra, set_dec, set_z = np.array(dat.ra), np.array(dat.dec), np.array(dat.z)
	d_file = home + 'tmp_stack/cluster/cluster_mask_%s_ra%.3f_dec%.3f_z%.3f_cat-corrected.fits'
	rule_file = 'tot_clust_rule-out_cat.csv'
	remain_file = 'tot_clust_remain_cat.csv'
	diffuse_identi_func(band[0], set_ra, set_dec, set_z, d_file, rule_file, remain_file,)

	print('cluster finished!')

	##### random imgs
	dat = pds.read_csv('random_tot-r-band_norm-img_cat.csv')
	set_ra, set_dec, set_z = np.array(dat.ra), np.array(dat.dec), np.array(dat.z)
	d_file = home + 'tmp_stack/random/random_mask_%s_ra%.3f_dec%.3f_z%.3f_cat-corrected.fits'
	rule_file = 'tot_random_rule-out_cat.csv'
	remain_file = 'tot_random_remain_cat.csv'
	diffuse_identi_func(band[0], set_ra, set_dec, set_z, d_file, rule_file, remain_file,)

	raise

if __name__ == "__main__":
	main()
